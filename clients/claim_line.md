# CLAIM_LINE (Acme Health)

## Purpose
Stores one record per service line within a claim, detailing the specific procedures, units, and amounts for each service. This table provides granular detail for claim analysis.

## Fields

| Field          | Meaning                                     | Data Type    | Example     |
|----------------|---------------------------------------------|--------------|-------------|
| CLAIM_ID       | Parent claim identifier                     | VARCHAR(50)  | 'ACMEH-C0012345' |
| LINE_NUMBER    | Line number within the claim (e.g., 1, 2) | INTEGER      | 1           |
| CPT_CODE       | Procedure code ([Glossary](glossary.md#cpt_code)) | VARCHAR(10)  | '99213'     |
| UNITS          | Number of billed units for the service      | INTEGER      | 1           |
| ALLOWED_AMOUNT | Contractually allowed amount ([Glossary](glossary.md#allowed_amount)) | DECIMAL(18,2)| 100.00      |
| BILLED_AMOUNT  | Amount billed by the provider               | DECIMAL(18,2)| 120.00      |
| PAID_LINE_AMOUNT | Amount paid for this specific line        | DECIMAL(18,2)| 80.00       |
| SERVICE_DATE   | Date the service was rendered               | DATE         | '2022-12-03'|

## Related Tables

-   [CLAIM_HEADER](clients/claim_header.md) (Many-to-one: Many CLAIM_LINEs to one CLAIM_HEADER via CLAIM_ID)

## Sample Data

```sql
SELECT
    CLAIM_ID,
    LINE_NUMBER,
    CPT_CODE,
    UNITS,
    PAID_LINE_AMOUNT
FROM
    ACMEHEALTH.CLAIM_LINE
WHERE
    CPT_CODE = '99213'
LIMIT 5;