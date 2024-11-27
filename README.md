# Backup and Recovery with AWS Backup
![backup-recovery-with-aws-backup.png](diagrams%2Fbackup-recovery-with-aws-backup.png)

This repository provides a solution for implementing backup and recovery with AWS Backup across multiple accounts and regions within an AWS organization.

The solution includes the following features:

* Deployment guide and CloudFormation templates for deploying and managing the solution
* CodePipeline for orchestrating and automating the management, changes, testing, and deployment of solution across your accounts and regions
* CodeBuild project for static analysis of CloudFormation templates using cfn-nag
* Vault, KMS Key, and service role for deployment of AWS Backup to each account and region
* Vault, KMS Key, and service role for centralized AWS Backup for secondary backup storage from all accounts and regions.
* Sample AWS Organizations Service Control Policy to limit sharing and copying of AWS Backup vaults to only AWS accounts within the AWS Organization.
* Restore testing plan and sample AWS Lambda validation function for secondary backups.
* Multi-region, multi-account design and implementation for AWS Backup framework controls and reports
* Multi-region, multi-account EC2 instances and related resources to demonstate solution features

This solution is designed to be modified to fit your specific requirements.

## Prerequisites
* AWS Organizations:  The solution is designed to standardize AWS Backup for the AWS organizations units you specify within an AWS Organization.  The following AWS Organizations features must be enabled:
  * CloudFormation StackSets
  * Backup Policies and Backup Monitoring
* Separate AWS Account for solution: A separate AWS account within your AWS Organizations must be selected to deploy and manage the solution.  Implementing the solution in a separate account improves security and reduces the need to provide access to your AWS Organizations management account.
* Separate AWS Account for secondary backups:  A secondary account is used as a secondary store for backup copies.  This account will receive a copy of each backup performed in the organization for the organization units you have specified in the solution.  You should choose an account where permissions have been limited appropriately to administrative users.  The solution utilizes a central AWS Backup Vault and KMS key in a region of your choice.  You may decide to use a different region than your backed up resources based on your requirements.


## Prepare

### Enable required AWS Organizations features and Delegated Administrator permissions

The Backup and Recovery with AWS Backup solution uses a service-managed StackSet to configure AWS Backup in accounts within the AWS Organization Units (OUs) you specify.  The solution utilizes service-managed CloudFormation StackSets to consistently deploy and manage required AWS Backup resources such as vaults, encryption keys, and IAM roles.  New accounts added to the target OUs will automatically be configured with the Backup and Recovery with AWS Backup solution.

You will need to enable trusted access between AWS CloudFormation StackSets and AWS Organizations.  You can [follow the directions in the CloudFormation documentation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-orgs-activate-trusted-access.html).

You will also need to enable trusted access for AWS Backup and turn on policy and monitoring access.  You can follow the [AWS Backup directions to enable trusted access](https://docs.aws.amazon.com/organizations/latest/userguide/services-that-can-integrate-backup.html#integrate-enable-ta-backup).

* In your AWS Organizations Management account, confirm that setup was successful:

      aws organizations list-aws-service-access-for-organization

You should see the following:
```json
        {
            "ServicePrincipal": "member.org.stacksets.cloudformation.amazonaws.com",
            "DateEnabled": "XXXX-XX-XXTXX:XX:XX.XXXXXX+XX:XX"
        },
        {
            "ServicePrincipal": "backup.amazonaws.com",
            "DateEnabled": "XXXX-XX-XXTXX:XX:XX.XXXXXX+XX:XX"
        }
```

### Register Delegated Administrator account 

#### **CloudFormation Service-Managed StackSets**
Your AWS Organizations management account is the only account by default that has rights to deploy service-managed CloudFormation stacksets.  However, you can register other accounts as delegated administrators for AWS Organizations features such as service-managed stack set deployments.  A specific account for tihs solution si defined as the **solution home account** and the selected region for the solution is called the **solution home region** where you will deploy the majority of the solution components.  This account must be registered as a delegated administrator because it will deploy and update the service-managed stacksets used in the solution.

Take the following steps to enable delegated administrator permissions for your organization:

* Register the solution home account as a delegated administrator: 

      aws organizations register-delegated-administrator --account-id=<Solution Home AWS Account Number> --service-principal=member.org.stacksets.cloudformation.amazonaws.com 

* Verify that the registration succeeded:

      aws organizations list-delegated-administrators

* Verify that the delegated service is enabled:

      aws organizations list-delegated-services-for-account --account-id <Solution Home AWS Account Number>

#### **AWS Backup Policy Management & Monitoring**

The solution manages backup policies and cross-account reporting for your AWS organization via CloudFormation.  In order for the solution to manage policies and establish organization-level monitoring and reporting you will need to register the solution account as a delegated administrator for AWS Backup.

Take the following steps to enable delegated administrator permissions for your organization:

* Register the solution home account as a delegated administrator:

      aws organizations register-delegated-administrator --account-id=<Solution Home AWS Account Number> --service-principal=backup.amazonaws.com 

* Verify that the registration succeeded:

      aws organizations list-delegated-administrators

* Verify that the delegated service is enabled:

      aws organizations list-delegated-services-for-account --account-id <Solution Home AWS Account Number>

### Grant the Solution Home Account Delegated Administrator permissions to manage AWS Organizations Backup Policies
Before you can manage and update AWS Organizations backup policies from another AWS account, you need to grant that account permissions via a [resource-based delegation policy](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_delegate_policies.html) in your AWS Organizations management account.

The [aws-backup-org-resource-policy-delegate-backup-policy-mgmt.yaml](./cloudformation/stacks/aws-backup-org-resource-policy-delegate-backup-policy-mgmt.yaml) CloudFormation template has been provided to deploy a resource-based delegation policy that grants the AWS account you have chosen for the solution to manage AWS Backup policies for the AWS organization.

Deploy this template in your AWS Organizations Management account using the AWS console or run this command using the AWS CLI.  

Make sure your permissions are set to your AWS Organizations management account before using this CLI command:

      aws cloudformation create-stack \
          --stack-name "aws-backup-org-resource-policy-delegate-backup-policy-mgmt"  \
          --template-body "file://cloudformation/stacks/aws-backup-org-resource-policy-delegate-backup-policy-mgmt.yaml" \
          --parameters ParameterKey=SolutionHomeAccountId,ParameterValue=<The AWS Account Id where you are deploying the solution> \
                       ParameterKey=pOrganizationRootId,ParameterValue=<The AWS Organization Root ID> \
                       ParameterKey=pOrganizationId,ParameterValue=<The AWS Organization ID> \
          --tags "Key"="Application","Value"="Backup and Recovery with AWS Backup Solution" \
          --region <run this command in one region of your choice>
### Gather Configuration Settings

Before you can deploy the solution, you will need to take note of the following settings:

---

#### GitHub Configuration
* **GitHub Repository**: The forked solution GitHub repository name (default: `backup-recovery-with-aws-backup`)
* **GitHub Branch**: Your repository branch to use (default: `main`)

#### GitHub Credentials
* **GitHub Username**: Your GitHub Username containing the forked solution repository.
* **GitHub Personal Access Token**: Your GitHub Personal Access Token you generated for CodePipeline integration.

---

#### Solution Configuration
* **AWS Organization ID**: The AWS Organizations ID where backup policies will be administered.
* **AWS Organization Management Account ID**: The AWS Organizations Management Account ID where backup policies will be administered.
* **Solution Home Organizational Unit (OU)**: The AWS Organizational Unit (OU) in which this solution home account lives.
* **Target Global Region**: Target region for global resources.
* **Target Regions**: Comma-separated list of regions that you want to configure for backup.
* **Target Organizational Units (OUs)**: List of OUs whose accounts you want to configure for backup.

---

#### Central Backup Account Configuration
* **AWS Backup Central Account OU**: The AWS OU for the central account that will be the secondary store for all accounts/regions. Secondary copies and restore testing will be in the selected account within this OU.
* **AWS Backup Central Account ID**: The AWS Account ID for the central account that will be the secondary store for all AWS Backups. Secondary copies and restore testing will be in this account.
* **AWS Backup Central Account Region**: The region for the central account that will be the secondary store for all AWS Backups. Secondary copies and restore testing will be in this region.

---

#### Restore Testing Configuration - Plan
* **Restore Test Schedule (CRON)**: The CRON job to initiate the restore test plan. (e.g., `cron(0 7 ? * 6 *)` for weekly on Saturday, at 07:00 UTC).
* **Recovery Points Selection Window (Days)**: The number of days to select recovery points. (default: `365`)
* **Restore Testing Start Window (Hours)**: The number of hours for the restore testing start window. (default: `1`)

---

#### Restore Testing Selection - EC2
* **Restore Subnet for EC2**: The restore subnet for EC2 restore testing.
* **Restore Security Group ID to use for EC2**: The restore security group IDs for EC2 restore testing.
* **Restore Validation Duration Time (Hours)**: The number of hours to keep the EC2 instance active for restore validation. (default: `1`)

---

#### Resource Point Selection Tags
* **Resource Point Selection Tag Key**: The tag key used for selecting resources (e.g., `backup`).
* **Resource Point Selection Tag Value**: The tag value used for selecting resources (e.g., `daily`).

---

#### Customer Specific Tags
* **Business Unit**: Business unit name. (default: `Engineering`)
* **Cost Center**: Cost center for AWS Services. (default: `00000`)
* **Environment**: Environment. (default: `development`)
* **Application Owner**: Email address of the application owner. (default: `someone@example.com`)
* **Application Name**: Application Name. (default: `Backup and Recovery with AWS Backup`)

---

#### AWS Backup Framework Configuration
* **Control #1 - Backup resources are included in at least one backup plan**: Evaluates if resources are included in at least one backup plan. (default: `true`)
* **Control #2 - Backup plan has minimum frequency and minimum retention**: Ensures backup frequency is at least x days and retention period is at least y days. (default: `true`)
* **Control #3 - Vaults prevent manual deletion of recovery points**: Ensures backup vaults do not allow manual deletion of recovery points except by certain IAM roles. (default: `false`)
* **Control #4 - Recovery points are encrypted**: Ensures recovery points are encrypted. (default: `true`)
* **Control #5 - Minimum retention established for recovery points**: Ensures retention period is at least x days. (default: `true`)
* **Control #6 - Cross-Region backup copy is scheduled**: Ensures resources create cross-region backup copies. (default: `false`)
* **Control #7 - Cross-account backup copy is scheduled**: Ensures resources have a cross-account backup copy configured. (default: `true`)
* **Control #8 - Backups are protected by AWS Backup Vault Lock**: Ensures resources have backups in locked backup vaults. (default: `false`)
* **Control #9 - Last recovery point was created**: Ensures a recovery point was created within the specified time frame. (default: `true`)
* **Control #10 - Restore time for resources meets target**: Ensures restore testing job completes within the target restore time. (default: `false`)

---

#### AWS Backup Report Configuration
* **Backup Audit Manager Report Feature** - Deploy Report Resources below. (default: `true`)
* **Report Plan #1 - RESOURCE_COMPLIANCE_REPORT**: Create a Resource Compliance Report Plan. This is only used if the value of "Backup Audit Manager Report Feature" is set to true. (default: `true`)
* **Report Plan #2 - CONTROL_COMPLIANCE_REPORT**: Create a Control Compliance Report Plan. This is only used if the value of "Backup Audit Manager Report Feature" is set to true. (default: `true`)
* **Report Plan #3 - BACKUP_JOB_REPORT**: Create a Backup Job Report Plan. This is only used if the value of "Backup Audit Manager Report Feature" is set to true. (default: `true`)
* **Report Plan #4 - COPY_JOB_REPORT**: Create a Copy Job Report Plan. This is only used if the value of "Backup Audit Manager Report Feature" is set to true. (default: `true`)
* **Report Plan #5 - RESTORE_JOB_REPORT**: Create a Restore Job Report Plan. This is only used if the value of "Backup Audit Manager Report Feature" is set to true. (default: `true`)

---

#### Demo Resources
* **Demo EC2 Instance Type**: Instance type for demo EC2 instances. (default: `t3.nano`)
* **Demo VPC CIDR Block**: CIDR block for the demo VPC. (default: `10.0.0.0/16`)
* **Demo Subnet CIDR Block**: CIDR block for the demo subnet. (default: `10.0.1.0/24`)
* **Tag Key for AWS Backup**: Tag key for demo resources to align with AWS Backup policy. (default: `backup`)
* **Tag Value for AWS Backup**: Tag value for demo resources to align with AWS Backup policy. (default: `daily`)

---

#### AWS Config Configuration Recorder
* **Auto-configuration of AWS Config Configuration Recorder**: Automatically configure a Configuration Recorder for each region. (default: `false`)
> ⚠️ **Warning:** If you want to deploy the recorder with Cloudformation(means you select true), please make sure there is no recorder in each region. Otherwise, an error will occur when deploying the template. 

> **Info:** If you select false, you can use AWS Systems Manager Quick Setup to create a configuration recorder across multiple organizational units (OUs) and AWS Regions using AWS best practices. For more information, see [Create an AWS Config configuration recorder using Quick Setup](https://docs.aws.amazon.com/systems-manager/latest/userguide/quick-setup-config.html) in the Systems Manager User Guide.
---  


# Deployment
The solution utilizes AWS CodePipeline for orchestration and deployment of AWS resources to your selected AWS organizational unit (OU) accounts.  

The default source code configuration in CodePipeline utilizes GitHub.  If you wish to use another source code provider then you can update the CodePipeline **SourceStage** in [_backup-recovery-with-aws-backup.yaml](_backup-recovery-with-aws-backup.yaml) CloudFormation template appropriately.

## GitHub Setup

### 1. Fork this GitHub repository
Fork the GitHub repository so that you can make necessary changes while still keeping track of new enhancements and updates to the solution.

Follow the instructions below, confirming that each created CloudFormation stack is in the **CREATE_COMPLETE** state 
before proceeding with the next step.

### 2. Generate a Personal Access Token (PAT) in GitHub
Before deploying the CloudFormation template, you'll need to create a Personal Access Token (PAT) in GitHub:

* Go to your GitHub account settings.
* Navigate to Developer Settings > Tokens (classic).
* Click Generate New Token and give it a descriptive name.
* Select the following scopes:
  * repo (Full control of private repositories)
  * admin:repo_hook (Full control of repository hooks)
* Generate the token and copy it.

You will use this token as a secret in AWS Systems Manager (SSM) to allow CodePipeline to access your GitHub repository.

### 3. Deploy the Primary Quick Start CloudFormation stack in your Selected Solution Home Account and Region
Login to the AWS console for your selected solution home account & region and deploy the [_backup-recovery-with-aws-backup.yaml](_backup-recovery-with-aws-backup.yaml) CloudFormation template.

### 4. Update the [aws-backup-org-policy.yaml](./cloudformation/stacks/aws-backup-org-policy.yaml) CloudFormation template

The [aws-backup-org-policy.yaml](./cloudformation/stacks/aws-backup-org-policy.yaml) CloudFormation template is used to manage your AWS Organizations Backup policies.  The template uses the [AWS::Organizations::Policy](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-organizations-policy.html) to manage Backup policies for the AWS Organization as a delegated administrator via CloudFormation.

Ensure that you have given your solution home account delegated administrator permissions as described in the first step of this deployment section.

The provided template uses the [Fn::ToJsonString](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-ToJsonString.html) CloudFormation transformation, allowing you to manage your [Backup Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_backup_syntax.html#backup-policy-syntax-reference) in YAML syntax within CloudFormation.

This example implements the following policy properties:

* For all supported resources in the target regions and target OUs that are tagged with the tag key **backup** and the tag value **daily**, perform a nightly backup at 05:00 UTC.  The backup will have a retention period of 35 days.  The backups will also be copied to the selected central backup vault.  If the backup doesn't complete in 1200 (20 hours) then it will be cancelled.
* For all supported resources in the target regions and target OUs that are tagged with the tag key **backup** and the tag value **monthly**, perform a monthly backup at 05:00 UTC on the first day of each month.  The backup will have a retention period of 366 days.  The backups will also be copied to the selected central backup vault.  If the backup doesn't complete in 1200 (20 hours) then it will be cancelled.

#### **REQUIRED**
At a minimum, update the **copy_actions** key with your central backup vault ARN in the [aws-backup-org-policy stack](./cloudformation/stacks/aws-backup-org-policy.yaml) CloudFormation template.  The key value has a placeholder called **<Replace with value from pCentralBackupVaultArn>**.  You must do this for each resource defined in the template.

You can retrieve the AWS Backup central vault ARN by logging into the **AWS Backup Central Account ID** and **AWS Backup Central Account Region** you specified when you deployed the solution.  Proceed to the **Vaults** section in AWS Backup console. 

### 5.  Enable the Stage Transition for DeployBackupOrgPolicy
By default, the DeployBackupOrgPolicy stage transition is disabled to allow you to update the [aws-backup-org-policy.yaml](./cloudformation/stacks/aws-backup-org-policy.yaml) CloudFormation template backup policy.  

Enable the stage transition in the AWS CodePipeline console after you have updated the policies and **copy_actions** keys with your central backup vault ARN.

## AWS Backup Service Control Policies
You can further refine security for your AWS Backup deployment by implementing organization-wide Service Control Policies for the **backup:CopyFromBackupVault** permission.

### Limit Copy From AWS Backup Vault To Central Vault
You can deploy the [limit-copy-from-vault-to-central-vault.yaml](cloudformation%2Fstacks%2Fscp%2Flimit-copy-from-vault-to-central-vault.yaml) CloudFormation template to limit AWS Backup Vault backup copies to be shared only with the solution's designated AWS Backup Central Vault.

This service control policies ensures that AWS organizations accounts do not share their backup copies with any other AWS Backup Vault other than the secondary copy in the central AWS Backup Vault account and region you have specified.

### Limit Copy From AWS Backup Vault to AWS Organization
You can deploy the [limit-copy-from-vault-to-org.yaml](cloudformation%2Fstacks%2Fscp%2Flimit-copy-from-vault-to-org.yaml) CloudFormation template to limit AWS Backup Vault copies to within the AWS Organization.  

This is less restrictive than the [limit-copy-from-vault-to-central-vault.yaml](cloudformation%2Fstacks%2Fscp%2Flimit-copy-from-vault-to-central-vault.yaml) CloudFormation template because it allows accounts within your AWS Backup account to potentially share their AWS Backup vault with other accounts within your AWS organization.

## Solution Components

#### **Solution Home Account:**
* CodePipeline - **backup-recovery-with-aws-backup**:  This pipeline orchestrates the deployment of all solution components.
* KMS Key for CodePipeline artifacts - **aws-backup-codepipeline-kms**
* IAM Service Role for AWS CloudFormation - **CloudFormationRole**
* Solution CodeBuild Projects:
  * **ValidateTemplates**: This CodeBuild project performs static analysis on the CloudFormation templates used in the solution using [cfn-nag](https://github.com/stelligent/cfn_nag).
* Deployment S3 Bucket (auto generated name):
* Systems Manager Parameter Store Parameters:
  The cloudformation stack requests the values of each of these parameters when you deploy the solution, grouped by area:
  * **/backup/org-id**:  The AWS Organizations ID where backup policies will be administered.
  * **/backup/bucket**:  S3 bucket used to store source artifacts for Backup and Recovery with AWS Backup solution.
  * **/backup/solution-ou**:  AWS AWS Organizations Unit for the Solution home account.
  * **/backup/central-account-ou**:  The AWS OU for the central account that will be the secondary store for all AWS Backups.  Secondary copies and restore testing will be in an account within this OU
  * **/backup/central-account-id**:  The AWS Account ID for the central account that will be the secondary store for all AWS Backups.  Secondary copies and restore testing will be in this account.
  * **/backup/central-account-region**:  The region for the central account that will be the secondary store for all AWS Backups.  Secondary copies and restore testing will be in this region.
  * **/backup/central-vault-arn**: The ARN for the Central Backup Vault that will be the secondary store for all AWS Backups.
  * **/backup/testing/restore-test-schedule**: The CRON job schedule for the restore test plan.
  * **/backup/testing/ec2/subnetId**:  The subnet for EC2 restore testing.
  * **/backup/testing/ec2/securityGroupIds**:  The restore security group IDs for EC2 restore testing.
  * **/backup/testing/ec2/validation-window-hours**:  The number of hours to keep the EC2 instance active for restore testing validation.
  * **/backup/testing/selection-window-days**:  The number of days to select recovery points.
  * **/backup/testing/start-window-hours**:  The number of hours for the restore testing start window.
  * **/backup/testing/ec2/tag-key**:  The tag key used for selecting resources.
  * **/backup/testing/ec2/tag-value**:  The tag value used for selecting resources.
  * **/backup/target/global-region**:  Target region for global resources for Backup and Recovery with AWS Backup solution
  * **/backup/target/regions**:  Target regions for Backup and Recovery with AWS Backup solution
  * **/backup/target/organizational-units**:  Target OUs for Backup and Recovery with AWS Backup solution
  * **/backup/control1**:  Do you want to evaluates if resources are included in at least one backup plan?
  * **/backup/demo/ec2-instance-type**:  The instance type for demo EC2 instances
  * **/backup/demo/vpc-cidr**:  The CIDR for the demo VPC
  * **/backup/demo/subnet-cidr**: The CIDR for the demo subnet
  * **/backup/demo/tag-key**: The tag key to apply to demo resources - align to AWS Backup policy
  * **/backup/demo/tag-value**: The tag value to apply to demo resources - align to AWS Backup policy
  * **/backup/control2**: Do you want to evaluate if backup frequency is at least x days and retention period is at least y days?
  * **/backup/control3**: Do you want to evaluate if backup vaults do not allow manual deletion of recovery points except by certain AWS Identity and Access Management (IAM) roles?
  * **/backup/control4**: Do you want to evaluate if the recovery points are encrypted?
  * **/backup/control5**: Do you want to evaluate if the recovery point retention period is at least x days?
  * **/backup/control6**: Do you want to evaluate if a resource is configured to create copies of its backups to another AWS Region?
  * **/backup/control7**: Do you want to evaluate if a resource has a cross-account backup copy configured?
  * **/backup/control8**: Do you want to evaluate if a resource is configured to have backups in a locked backup vault?
  * **/backup/control9**: Do you want to evaluate if a recovery point was created within the specified time frame?
  * **/backup/control10**: Do you want to evaluate if the restore testing job completed within the target restore time?
  * **/backup/backupplan1**: Do you want to create a Resource Compliance Report Plan?
  * **/backup/backupplan2**: Do you want to create a Control Compliance Report Plan?
  * **/backup/backupplan3**: Do you want to create a Backup Job Report Plan?
  * **/backup/backupplan4**: Do you want to create a Copy Job Report Plan?
  * **/backup/backupplan5**: Do you want to create a Restore Job Report Plan?

#### **Central AWS Backup Account:**

* ##### Secondary Storage:
  * Central AWS Backup Vault (**AWSBackupSolutionCentralVault**)
  * Central AWS Backup KMS Key (**AWSBackupSolutionCentralKey**)
  * Central AWS Backup Service Role (**AWSBackupSolutionCentralAccountRole**)

* ##### Restore Testing and Validation:
  * AWS Backup Restore Testing Role (AWSBackupRestoreTestingRole)
  * AWS Backup Restore Testing Plan (RestoreTestPlan)
  * AWS Lambda Execution Role (AWSBackupRestoreTestValidationLambdaExecutionRole)
  * AWS Lambda Restore Testing Validation Function (RestoreTestingValidationLambda)
  * AWS Events Rule - Restore Job Completed (BackupRestoreJobStateChangeRule)

#### **Each Target AWS Organizations Account for Backup:**
* AWS Backup Account Vault (**AWSBackupSolutionVault**)
* AWS Backup Account KMS Key (**AWSBackupSolutionKey**)
* AWS Backup Account Service Role (**AWSBackupSolutionRole**)
* AWS Config Bucket (rConfigBucket)
* AWS Config Recorder (rConfigRecorder)
* AWS Backup Audit Frameworks (rFramework)
* Demo Resources
  * VPC
  * Subnet
  * Internet Gateway
  * Route Table
  * 3 EC2 Launch Templates
  * 3 EC2 Fleets
  * Security Group
  * IAM Role and corresponding EC2 Instance Profile


## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

