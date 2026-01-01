import pulumi as p
import pulumi_minio as minio


class MimirBuckets(p.ComponentResource):
    def __init__(
        self,
        name: str,
    ):
        super().__init__(f'lab:mimir_buckets:{name}', name)

        s3_config = p.Config().require_object('s3')

        # Create minio provider
        minio_opts = p.ResourceOptions(
            provider=minio.Provider(
                'minio',
                minio_server=f'{s3_config["endpoint"]}:443',
                minio_user=s3_config['admin-user'],
                minio_password=p.Output.secret(s3_config['admin-password']),
                minio_ssl=True,
                opts=p.ResourceOptions(parent=self),
            ),
            parent=self,
        )

        bucket_blocks = minio.S3Bucket(
            'mimir-blocks',
            bucket='mimir-blocks',
            opts=minio_opts,
        )

        bucket_alertmanager = minio.S3Bucket(
            'mimir-alertmanager',
            bucket='mimir-alertmanager',
            opts=minio_opts,
        )

        bucket_ruler = minio.S3Bucket(
            'mimir-ruler',
            bucket='mimir-ruler',
            opts=minio_opts,
        )

        policy = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': ['s3:ListBucket'],
                    'Effect': 'Allow',
                    'Resource': [
                        bucket_blocks.arn,
                        bucket_alertmanager.arn,
                        bucket_ruler.arn,
                    ],
                },
                {
                    'Action': ['s3:*'],
                    'Effect': 'Allow',
                    'Resource': [
                        p.Output.format('{}/*', bucket_blocks.arn),
                        p.Output.format('{}/*', bucket_alertmanager.arn),
                        p.Output.format('{}/*', bucket_ruler.arn),
                    ],
                },
            ],
        }
        policy = minio.IamPolicy(
            'mimir',
            policy=p.Output.json_dumps(policy),
            opts=minio_opts,
        )

        bucket_user = minio.IamUser(
            'mimir',
            opts=minio_opts,
        )

        minio.IamUserPolicyAttachment(
            'mimir',
            user_name=bucket_user.name,
            policy_name=policy.name,
            opts=minio_opts,
        )

        # Export infos for mimir
        self.bucket_user = bucket_user
        self.bucket_blocks = bucket_blocks
        self.bucket_alertmanager = bucket_alertmanager
        self.bucket_ruler = bucket_ruler

        self.register_outputs({})
