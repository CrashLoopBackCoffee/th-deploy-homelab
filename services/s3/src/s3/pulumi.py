import pulumi as p
import pulumi_minio
import pulumi_onepassword as onepassword


def create_pulumi_bucket(
    minio_provider: pulumi_minio.Provider,
):
    minio_opts = p.ResourceOptions(provider=minio_provider)
    bucket = pulumi_minio.S3Bucket(
        'pulumi',
        bucket='pulumi',
        opts=minio_opts,
    )

    pulumi_minio.S3BucketVersioning(
        'pulumi',
        bucket=bucket.bucket,
        versioning_configuration={'status': 'Enabled'},
        opts=minio_opts,
    )

    policy_data = {
        'Version': '2012-10-17',
        'Statement': [
            {
                'Action': ['s3:ListBucket'],
                'Effect': 'Allow',
                'Resource': [
                    bucket.arn,
                ],
            },
            {
                'Action': ['s3:*'],
                'Effect': 'Allow',
                'Resource': [
                    p.Output.format('{}/*', bucket.arn),
                ],
            },
        ],
    }

    policy = pulumi_minio.IamPolicy(
        'pulumi',
        policy=p.Output.json_dumps(policy_data),
        opts=minio_opts,
    )

    bucket_user = pulumi_minio.IamUser(
        'pulumi',
        name='pulumi',
        opts=minio_opts,
    )

    pulumi_minio.IamUserPolicyAttachment(
        'pulumi',
        user_name=bucket_user.name,
        policy_name=policy.name,
        opts=minio_opts,
    )

    onepassword.Item(
        's3-pulumi',
        title='Pulumi S3 Token',
        # Pulumi vault
        vault='mf5hvtoot2hvdylkce6hxdpqmi',
        username=bucket_user.name,
        password=bucket_user.secret,
    )
