# pylint: disable = C0103, R0902, W1203, C0301, W0311
import time
import json
import logging
import urllib3
import boto3
from botocore.config import Config
from os import getenv
from time import sleep

from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)
AWS_REGION = getenv('AWS_REGION')


def boto3_client(resource, region=AWS_REGION, assumed_credentials=None):
    config = Config(
        retries=dict(
            max_attempts=40
        ),
        region_name=region
    )
    if assumed_credentials:
        client = boto3.client(
            resource,
            aws_access_key_id=assumed_credentials['AccessKeyId'],
            aws_secret_access_key=assumed_credentials['SecretAccessKey'],
            aws_session_token=assumed_credentials['SessionToken'],
            config=config
        )
    else:
        client = boto3.client(
            resource,
            config=config
        )

    return client


def assume_role(account_number, session_name):
    sts_client = boto3_client('sts')
    assumed_role_object = sts_client.assume_role(
        RoleArn="arn:aws:iam::" + account_number + ":role/BackupOrgPolicyManagerOrgAdmin",
        RoleSessionName=session_name
    )

    assumed_credentials = assumed_role_object['Credentials']
    return assumed_credentials


def get_policy(policy_content, target_regions, variables=[]):
    """
    Helper function for getting the policy contents from the event object. This function
    will extract the policy from an S3 location if PolicyBucket and PolicyLocation is provided
    """
    try:
        if 'S3' in policy_content:
            if 'PolicyBucket' in policy_content['S3']:
                s3_bucket = policy_content['S3']['PolicyBucket']
            else:
                logger.error('S3 specified but no "PolicyBucket" indicated')
                raise Exception('S3 specified but no "PolicyBucket" indicated')

            if 'PolicyKey' in policy_content['S3']:
                s3_object = policy_content['S3']['PolicyKey']
            else:
                logger.error('S3 specified but no "PolicyKey" indicated')
                raise Exception('S3 specified but no "PolicyKey" indicated')
            s3 = boto3.resource('s3')
            policy_file = s3.Object(s3_bucket, s3_object)
            policy_content = policy_file.get()['Body'].read().decode('utf-8')

        # logger.info(f"policy_contents : {policy_contents}")
        # Check for replacement variables
        for variable in variables:
            for key, value in variable.items():
                logger.info(f"Replacing Key : {key} with value : {value}")
                policy_content = policy_content.replace(key, value)

        policy_content = json.loads(policy_content)
        logger.info(f'policy is: {policy_content}')

        for plan in policy_content['plans'].keys():
            logger.info(f'processing plan: {plan}')
            policy_content['plans'][plan]['regions'] = {'@@append': target_regions}
        return policy_content
    except Exception as e:
        logger.error("Exception getting policy: {}".format(e))
        raise


def check_properties(event):
    abort = False
    properties = {}
    msg = "SUCCESS"

    if 'ResourceProperties' in event:
        if 'PolicyName' in event['ResourceProperties']:
            properties['PolicyName'] = event['ResourceProperties']['PolicyName']
        else:
            msg = "No PolicyName specified in event['ResourceProperties']"
            logger.error(msg)
            abort = True

        if 'PolicyRegions' in event['ResourceProperties']:
            properties['PolicyRegions'] = event['ResourceProperties']['PolicyRegions']
        else:
            msg = "'PolicyRegions' has not been specified in 'ResourceProperties'"
            logger.error(msg)
            abort = True

        if 'OrgManagementAccount' in event['ResourceProperties']:
            properties['OrgManagementAccount'] = event['ResourceProperties']['OrgManagementAccount']
        else:
            msg = "'OrgManagementAccount' has not been specified.  This is required to manage backup policies in the org"
            logger.error(msg)

        if 'PolicyType' in event['ResourceProperties']:
            properties['PolicyType'] = event['ResourceProperties']['PolicyType']
        else:
            msg = "'PolicyType' has not been specified.  This is required to manage backup policies in the org"
            logger.error(msg)
            abort = True

        if 'PolicyDescription' in event['ResourceProperties']:
            properties['PolicyDescription'] = event['ResourceProperties']['PolicyDescription']
        else:
            msg = "'PolicyDescription' has not been specified.  This is required to manage backup policies in the org"
            logger.error(msg)
            abort = True

        if 'PolicyTargets' in event['ResourceProperties']:
            properties['PolicyTargets'] = event['ResourceProperties']['PolicyTargets']
        else:
            msg = "No policy targets specified in 'ResourceProperties'"
            logger.error(msg)
            abort = True

        if 'PolicyContent' in event['ResourceProperties']:
            properties['PolicyContent'] = event['ResourceProperties']['PolicyContent']
        else:
            msg = "'PolicyContent' has not been specified.  This is required to manage backup policies in the org"
            logger.error(msg)
            abort = True

        if 'Variables' in event['ResourceProperties']:
            properties['Variables'] = event['ResourceProperties']['Variables']
        else:
            properties['Variables'] = []
            logger.info(
                "'Variables' has not been specified.")

    else:
        logger.error("No 'ResourceProperties' in event")
        abort = True

    if abort:
        return {
            'success': False,
            'message': msg
        }
    else:
        return {
            'success': True,
            'properties': properties
        }


def lambda_handler(event, context):
    """
    Main Lambda handler function. This function will handle the Create, Update and Delete operation requests
    from CloudFormation
    """
    try:
        # create physical resource id

        status = 'SUCCESS'

        if 'PhysicalResourceId' in event:
            physical_resource_id = event['PhysicalResourceId']
            logger.info(f"PhysicalResourceId is {physical_resource_id}")
        else:
            logger.info('No PhysicalResourceId in request, setting to logical id')
            physical_resource_id = event['LogicalResourceId']

        logger.info(f"BackupOrgPolicyManager Request: {event}")

        resource_action = event['RequestType']

        if resource_action == 'Delete' and physical_resource_id == event['LogicalResourceId']:
            response_data = {
                'Message': 'Nothing to delete'
            }
            status = 'SUCCESS'
            send(event, context, status, response_data, physical_resource_id)
            return False

        properties = check_properties(event)

        if properties['success']:
            properties = properties['properties']
        else:
            response_data = {
                'Message': properties['message']
            }
            status = 'FAILED'
            send(event, context, status, response_data, physical_resource_id)
            return False

        if resource_action == 'Create':
            response_data = create(properties)

            if response_data:
                physical_resource_id = response_data['PolicyId']
                send(event, context, status, response_data, physical_resource_id)
            else:
                response_data = {
                    'Message': 'Policy creation and attachment failed'
                }
                status = 'FAILED'
                send(event, context, status, response_data, physical_resource_id)
                return False

        elif resource_action in ('Delete', 'Update'):
            assume_role_creds = assume_role(properties['OrgManagementAccount'],
                                            'BackupOrgPolicyManagerUpdateDelete')
            org_client = boto3_client('organizations', AWS_REGION, assume_role_creds)
            logger.info(
                f" Action: {resource_action} policy, policy_type: {properties['PolicyType']}, policy_prefix : {properties['PolicyName']}")
            response = org_client.list_policies(Filter=properties['PolicyType'])
            policyList = list(
                filter(lambda item: item['Name'].startswith(properties['PolicyName']), response["Policies"]))
            logger.info(f"Policy Found : {policyList}, Length : {len(policyList)}")

            if len(policyList) == 0 and resource_action == 'Delete':
                logger.error(f"Policy not found with prefix : {properties['PolicyName']} for delete, continuing")
                response_data = {
                    'Message': 'Policy not found for prefix : ' + properties['PolicyName'] + ' skipping delete'
                }
                status = 'SUCCESS'

            elif len(policyList) == 0 and resource_action == 'Update':
                logger.error(f"Policy not found with prefix : {properties['PolicyName']}")
                response_data = {
                    'Message': 'Policy not found for prefix : ' + properties['PolicyName']
                }
                status = 'FAILED'
            else:
                for policy in policyList:
                    policy_id = policy['Id']
                    org_client = boto3_client('organizations', AWS_REGION, assume_role_creds)

                    response = org_client.list_targets_for_policy(PolicyId=policy_id)
                    if 'Targets' in response:

                        curr_policy_target_list = []
                        for target in response['Targets']:
                            curr_policy_target_list.append(target['TargetId'])

                        # Detach the policy from existing list
                        detach_policy_from_target_list(curr_policy_target_list, policy_id, assume_role_creds)

                    # delete policies neverthless to allow new creation
                    try:
                        response = org_client.delete_policy(PolicyId=policy_id)
                        logger.info(f"deletePolicy response: {response}")
                    except Exception as e:  # pylint: disable = W0703
                        logger.error(str(e))

                if resource_action == 'Delete':
                    response_data = {'Message': 'Policy(s) deleted successfully'}
                    status = 'SUCCESS'
                elif resource_action == 'Update':
                    # Create and attach policies with new contents
                    response_data = create(properties)

                    if not response_data:
                        response_data = {
                            'Message': 'Policy creation and attachment failed'
                        }
                        status = 'FAILED'
                    else:
                        status = 'SUCCESS'
            send(event, context, status, response_data, physical_resource_id)

        else:
            logger.error(f"Unexpected Action : {resource_action}")
            response_data = {
                'Message': 'Unexpected event received from CloudFormation'
            }
            status = 'FAILED'
            send(event, context, status, response_data, physical_resource_id)
    except Exception as exc:
        logger.error(f"Exception: {str(exc)}")
        response_data = {
            'Message': str(exc)
        }
        status = 'FAILED'
        send(event, context, status, response_data, physical_resource_id)
        raise


def create(properties):
    policy_contents = get_policy(properties['PolicyContent'], properties['PolicyRegions'],
                                 properties['Variables'])
    logger.debug(f"Policy contents are: {policy_contents}")
    logger.info("'Create' action initiated")
    assume_role_creds = assume_role(properties['OrgManagementAccount'], 'BackupOrgPolicyManagerLambdaCreate')
    policy_id = create_and_attach_policies(properties['PolicyName'], properties['PolicyDescription'],
                                           properties['PolicyType'],
                                           policy_contents,
                                           properties['PolicyTargets'], assume_role_creds)

    if policy_id:
        response_data = {
            'PolicyName': properties['PolicyName'],
            'PolicyId': policy_id,
            'PolicyType': properties['PolicyType'],
            'PolicyTargets': properties['PolicyTargets'],
            'Message': 'Policies created and attached successfully'
        }

        return response_data
    else:
        return False


def create_and_attach_policies(policy_name, policy_description, policy_type, policy_content, policy_target_list,
                               assume_role_creds=None):
    """
    Helper function to create and attach the policies to the targets
    """
    try:
        logger.info(f"Create and update policy with contents : {json.dumps(policy_content)} for name : {policy_name}")
        org_client = boto3_client('organizations', AWS_REGION, assume_role_creds)
        response = org_client.create_policy(
            Content=json.dumps(policy_content),
            Description=policy_description,
            Name=policy_name,
            Type=policy_type
        )

        if not 'Policy' in response:
            logger.error("Error no policy received in response, returning..")
            return False
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConcurrentModificationException':
            logger.info("Concurrent creation detected, sleeping 5s and trying again..")
            sleep(5)
            response = org_client.create_policy(
                Content=json.dumps(policy_content),
                Description=policy_description,
                Name=policy_name,
                Type=policy_type
            )
        else:
            logger.error("Error occurred creating policy {}: {}".format(policy_name, e))
            return False

    logger.debug(f"Response: {response}")
    policy_id = response['Policy']['PolicySummary']['Id']

    logger.info(f'Policy creation complete, policy ID :{policy_id}, policy_name :{policy_name}')

    logger.info(f"attach_policy for {policy_id} on {policy_target_list}")
    # Attach the policy in target accounts
    for policyTarget in policy_target_list:
        try:
            # To avoid ConcurrentModificationException
            time.sleep(int(5))
            logger.info(f"Attaching {policy_id} on Account {policyTarget}")
            org_client.attach_policy(PolicyId=policy_id,
                                     TargetId=policyTarget)

            logger.info(f"Attached {policy_id} on Account {policyTarget}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConcurrentModificationException':
                logger.info("Concurrent update detected when attaching policy, sleeping 5s and trying again..")
                sleep(5)
                org_client.attach_policy(PolicyId=policy_id,
                                         TargetId=policyTarget)

                logger.info(f"Attached {policy_id} on Account {policyTarget}")
            else:
                logger.error("Error occurred creating policy {}: {}".format(policy_name, e))

        except Exception as e:  # pylint: disable = W0703
            logger.error(str(e))

    return policy_id


def detach_policy(org_client, policy_id, policy_target):
    """
    Helper function to detach the specified policy from policy_target
    """
    try:
        logger.info(f"Detaching {policy_id} from Account {policy_target}")
        response = org_client.detach_policy(PolicyId=policy_id,
                                            TargetId=policy_target)
        logger.info(f"Detached {policy_id} from Account {policy_target}, Response : {response}")
    except org_client.exceptions.PolicyNotAttachedException:
        logger.info('Ignoring error to continue trying for further detachments.')

    except ClientError as e:
        if e.response['Error']['Code'] == 'ConcurrentModificationException':
            logger.info("Concurrent update detected when detaching policy, sleeping 5s and trying again..")
            sleep(5)
            response = org_client.detach_policy(PolicyId=policy_id,
                                                TargetId=policy_target)
            logger.info(f"Detached {policy_id} from Account {policy_target}, Response : {response}")
        else:
            logger.error("Error occurred detaching policy {}: {}".format(policy_id, e))


def detach_policy_from_target_list(policy_target_list, policy_id, assumed_role_creds=None):
    """
    Helper function to detach the specified policy from policy_target_list
    """
    # Detach the policy in target accounts
    org_client = boto3_client('organizations', AWS_REGION, assumed_role_creds)
    for policy_target in policy_target_list:
        try:
            detach_policy(org_client, policy_id, policy_target)
        except org_client.exceptions.PolicyInUseException:
            time.sleep(int(1))
            detach_policy(org_client, policy_id, policy_target)

        except org_client.exceptions.PolicyNotAttachedException:
            logger.info('Ignoring error to continue trying for further detachments.')


# def update_policy(policy_id, policy_content):
#     """
#     Helper function update the policy at the organization level.
#     """
#     logger.info(f"update_policy for policy_id : {policy_id}")
#     org_client.update_policy(PolicyId=policy_id, Content=json.dumps(policy_content))


def send(event, context, response_status, response_data, physical_resource_id,
         no_echo=False):  # pylint: disable = R0913
    """
    Helper function for sending updates on the custom resource to CloudFormation during a
    'Create', 'Update', or 'Delete' event.
    """

    http = urllib3.PoolManager()
    response_url = event['ResponseURL']

    json_response_body = json.dumps({
        'Status': response_status,
        'Reason': response_data['Message'] + f', See the details in CloudWatch Log Stream: {context.log_stream_name}',
        'PhysicalResourceId': physical_resource_id,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'NoEcho': no_echo,
        'Data': response_data
    }).encode('utf-8')

    headers = {
        'content-type': '',
        'content-length': str(len(json_response_body))
    }

    try:
        http.request('PUT', response_url,
                     body=json_response_body, headers=headers)
    except Exception as e:  # pylint: disable = W0703
        logger.error(e)
