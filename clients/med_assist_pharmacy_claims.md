# PHARMACY_CLAIMS (MedAssist)

## Purpose
Records each prescription filled by a member, including drug details, dispensing pharmacy, and costs. Essential for drug utilization review and fraud detection.

## Fields

| Field           | Meaning                                     | Data Type    | Example          |
|-----------------|---------------------------------------------|--------------|------------------|
| RX_CLAIM_ID     | Unique pharmacy claim identifier            | VARCHAR(50)  | 'MEDA-RX001001'  |
| MEMBER_ID       | Member identifier                           | VARCHAR(50)  | 'MEM-55443'      |
| PHARMACY_ID     | Identifier of the dispensing pharmacy       | VARCHAR(50)  | 'PHARM-0123'     |
| NDC_CODE        | National Drug Code                          | VARCHAR(11)  | '00002816901'    |
| FILL_DATE       | Date the prescription was filled            | DATE         | '2023-04-20'     |
| DAYS_SUPPLY     | Number of days the prescription is for      | INTEGER      | 30               |
| QUANTITY_DISPENSED| Number of units (pills, ml) dispensed     | DECIMAL(10,2)| 90.00            |
| TOTAL_PAID_AMOUNT| Total amount paid by plan for prescription | DECIMAL(18,2)| 45.50            |
| COPAY_AMOUNT    | Amount paid by the member as co-pay         | DECIMAL(18,2)| 10.00            |

## Related Tables

-   [DRUG_CODES](clients/med_assist_drug_codes.md) (Many-to-one: Many PHARMACY_CLAIMS to one DRUG_CODES via NDC_CODE)

## Sample Data

```sql
SELECT
    RX_CLAIM_ID,
    MEMBER_ID,
    NDC_CODE,
    FILL_DATE,
    TOTAL_PAID_AMOUNT
FROM
    MEDASSIST.PHARMACY_CLAIMS
WHERE
    FILL_DATE >= '2023-04-01'
LIMIT 5;