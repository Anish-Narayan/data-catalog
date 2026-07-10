# CLAIM_HEADER (Acme Health)

## Purpose
Stores one record per claim, containing high-level information about the claim submission. This table is central to understanding the overall status and financial outcome of a claim.

## Fields

| Field        | Meaning                                 | Data Type   | Example          |
|--------------|-----------------------------------------|-------------|------------------|
| CLAIM_ID     | Unique claim identifier                 | VARCHAR(50) | 'ACMEH-C0012345' |
| MEMBER_ID    | Member identifier                       | VARCHAR(50) | 'MEM-98765'      |
| PROVIDER_ID  | Billing provider unique identifier      | VARCHAR(50) | 'PROV-ABC001'    |
| PAID_AMOUNT  | Amount paid after adjudication          | DECIMAL(18,2)| 150.75           |
| CLAIM_STATUS | Current status of the claim             | VARCHAR(20) | 'Paid'           |
| SUBMISSION_DATE| Date the claim was submitted          | DATE        | '2023-01-15'     |
| SERVICE_START_DATE | Start date of services on claim   | DATE        | '2022-12-01'     |
| SERVICE_END_DATE | End date of services on claim       | DATE        | '2022-12-05'     |

## Related Tables

-   [CLAIM_LINE](clients/claim_line.md) (One-to-many: One CLAIM_HEADER to many CLAIM_LINEs)
-   [MEMBER_DEMOGRAPHICS](clients/acme_health_member_demographics.md) (Many-to-one: Many CLAIM_HEADERs to one MEMBER_DEMOGRAPHICS via MEMBER_ID)

## Sample Data

```sql
SELECT
    CLAIM_ID,
    MEMBER_ID,
    PAID_AMOUNT,
    CLAIM_STATUS
FROM
    ACMEHEALTH.CLAIM_HEADER
WHERE
    SUBMISSION_DATE >= '2023-01-01'
LIMIT 5;