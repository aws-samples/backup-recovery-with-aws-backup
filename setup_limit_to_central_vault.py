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
@click.option("--org", required=True, help='Enter the AWS Account ID that will be used to store copies of backups from AWS Organization Member Accounts.  AWS Organization member accounts will not be allowed to share backup vaults with any other account other than the one indicated.')
@click.option("--centralregion", required=False, default=None, help='Enter the region of the AWS Backup Vault in the central account to which backups can be shared.  If specified, AWS Organization member accounts will not be allowed to share backup vaults with a backup vault in any other region other than the one indicated.')
@click.option("--centralvault", required=False, default=None, help='Enter the name of the AWS Backup Vault in the central account to which backups can be shared.  If specified, AWS Organization member accounts will not be allowed to share backup vaults with any other backup vault other than the one named.')
@click.option("--policyname", required=False, default="BlockSharingAWSBackupVaults", help='Enter a custom name for the Service Control Policy')
@click.option("--policydescription", required=False,
              default="This policy prevents sharing of AWS Backup vaults with any account other than a single designated AWS account for centralized backup copy storage.",
              help='Enter a custom description for the Service Control Policy')
def setup(centralaccount, centralvault, centralregion, policyname, policydescription):
    try:
        f = open("LimitBackupVaultSharingToCentralVault.json", "r")
        policy = f.read()
        logger.info('policy start is: ')
        policy = policy.replace("<CentralAccountId>", centralaccount)
        if centralvault is not None:
            policy = policy.replace("<CentralVault>", centralvault)
        else:
            policy = policy.replace("<CentralVault>", "*")

        if centralregion is not None:
            policy = policy.replace("<CentralRegion>", centralregion)
        else:
            policy = policy.replace("<CentralRegion>", "*")

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
