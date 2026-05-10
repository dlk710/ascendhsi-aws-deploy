# AWS Human Access Runbook

Updated: 2026-05-10

This document records how humans should access the Ascend dev AWS account without using root for daily work.

## Current Dev Account

- Account ID: `027903151318`
- Account alias: `ascendhsi-dev`
- Console URL: `https://ascendhsi-dev.signin.aws.amazon.com/console`
- Region: `us-east-2`
- Account type today: standalone AWS account, not yet attached to AWS Organizations
- IAM Identity Center status: not enabled in this account at the time of setup

## Root User Rule

Use root only for break-glass or root-only actions such as account recovery, billing ownership changes, and Identity Center/Organizations bootstrap work.

For normal engineering and AWS administration, use the IAM user below and switch into an MFA-required role.

## Human Console User

- IAM user: `lohith-dev-admin`
- Access keys: none
- Login profile: enabled with password reset required on first login
- Direct permissions: intentionally narrow
- Allowed direct actions:
  - change own password
  - manage own MFA device
  - assume the approved Ascend dev roles

The temporary first-login password was stored in the local macOS Keychain under:

```text
service: ascend-aws-dev-temp-password
account: lohith-dev-admin
```

Retrieve it locally when needed:

```bash
security find-generic-password -a lohith-dev-admin -s ascend-aws-dev-temp-password -w
```

Delete the Keychain item after the first successful password reset.

## IAM Roles

All roles trust only `arn:aws:iam::027903151318:user/lohith-dev-admin` and require MFA through the trust policy condition `aws:MultiFactorAuthPresent=true`.

| Role | Managed policies | Intended use |
| --- | --- | --- |
| `AscendDevReadOnlyRole` | `ReadOnlyAccess` | Safe review, auditing, and non-mutating inspection. |
| `AscendDevPowerUserRole` | `PowerUserAccess`, `IAMReadOnlyAccess` | Daily development work that should not manage IAM directly. |
| `AscendDevAdminRole` | `AdministratorAccess` | Terraform, IAM, security, and break-glass admin tasks inside dev. |

## First Login Steps

1. Open `https://ascendhsi-dev.signin.aws.amazon.com/console`.
2. Sign in as `lohith-dev-admin`.
3. Use the temporary password from Keychain.
4. Reset the password when prompted.
5. Add MFA for the IAM user before switching roles.
6. Switch role into `AscendDevPowerUserRole` for normal work.
7. Use `AscendDevAdminRole` only when PowerUser cannot complete the task.

Direct switch-role links after login:

```text
https://signin.aws.amazon.com/switchrole?account=027903151318&roleName=AscendDevReadOnlyRole&displayName=AscendDevReadOnly
https://signin.aws.amazon.com/switchrole?account=027903151318&roleName=AscendDevPowerUserRole&displayName=AscendDevPowerUser
https://signin.aws.amazon.com/switchrole?account=027903151318&roleName=AscendDevAdminRole&displayName=AscendDevAdmin
```

## CLI Guidance

Prefer IAM Identity Center for CLI once the AWS Organization and Identity Center setup is completed.

Until then, avoid creating long-lived access keys for human users. If CLI access is absolutely required before Identity Center is available, use temporary session credentials and rotate them quickly.

## Future Target

Move human access to AWS IAM Identity Center after the account is attached to the planned AWS Organization.

Target permission sets:

- `ReadOnly`
- `DeveloperPowerUser-NonProd`
- `BreakGlassAdmin`

At that point, retire direct IAM human users and use Identity Center assignments instead.
