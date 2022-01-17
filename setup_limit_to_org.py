import boto3
import logging
from os import getenv
import sys
import click

logger = logging.getLogger()
handler = logging.StreamHandler(sys.stdout)
log_level = getenv("LOGLEVEL", "INFO")
level = logging.getLevelName(log_level)
logger.setLevel(level)
logger.addHandler(handler)


@click.command()
@click.option("--org", required=True, help='Enter your AWS Organizations ID.  Member accounts will not be allowed to share their backup vault with any accounts outside of the organization.')
@click.option("--policyname", required=False, default="BlockSharingAWSBackupVaultsOutsideOrg", help='Enter a custom name for the Service Control Policy')
@click.option("--policydescription", required=False,
              default="This policy prevents sharing of AWS Backup vaults with any account that is not a member of the AWS organization.",
              help='Enter a custom description for the Service Control Policy')

def setup(org, policyname, policydescription):
    try:
        f = open("LimitBackupVaultSharingToOrg.json", "r")
        policy = f.read()
        logger.info('policy start is: ')
        policy = policy.replace("<OrgId>", org)

        logger.info('Policy being applied is: {}'.format(policy))

        client = boto3.client('organizations')
        create_scp_info = {'Content': policy,
                           'Description': policydescription,
                           'Name': policyname,
                           'Type': 'SERVICE_CONTROL_POLICY',
                           'Tags': [
                               {
                                   'Key': 'string',
                                   'Value': 'string'
                               }
                           ]
                           }
        response = client.create_policy(**create_scp_info)

        logger.info("Response: {}".format(response))

    except Exception as e:
        # If any other exceptions which we didn't expect are raised
        # then fail and log the exception message.
        logger.error('Error applying service control policy: {}'.format(e))
        raise


setup()
