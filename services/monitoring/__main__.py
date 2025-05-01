"""A Python Pulumi program"""

import pulumi as p

if p.get_stack() == 'dev':
    from monitoring.main_legacy import main_legacy

    main_legacy()
else:
    from monitoring.main import main

    main()
