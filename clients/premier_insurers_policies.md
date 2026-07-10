# POLICIES (Premier Insurers)

## Purpose
Contains detailed information about each insurance policy, including policy type, coverage details, and premium amounts.

## Fields

| Field           | Meaning                                     | Data Type    | Example          |
|-----------------|---------------------------------------------|--------------|------------------|
| POLICY_ID       | Unique policy identifier                    | VARCHAR(50)  | 'PRMI-POL00123'  |
| POLICY_HOLDER_ID| Parent policy holder identifier             | VARCHAR(50)  | 'PRMI-PH00100'   |
| POLICY_TYPE     | Type of insurance (e.g., Auto, Home, Life)  | VARCHAR(50)  | 'Auto'           |
| COVERAGE_START_DATE | Date policy coverage began              | DATE         | '2023-01-01'     |
| COVERAGE_END_DATE | Date policy coverage ends                 | DATE         | '2024-01-01'     |
| PREMIUM_AMOUNT  | Annual premium amount                       | DECIMAL(18,2)| 1200.00          |
| STATUS          | Policy status (e.g., Active, Lapsed, Cancelled)| VARCHAR(20)  | 'Active'         |
| VEHICLE_VIN     | Vehicle Identification Number (for Auto)    | VARCHAR(17)  | '1FAFP38R6G2XXXX'|

## Related Tables

-   [POLICY_HOLDERS](clients/premier_insurers_policy_holders.md) (Many-to-one: Many POLICIES to one POLICY_HOLDERS via POLICY_HOLDER_ID)

## Sample Data

```sql
SELECT
    POLICY_ID,
    POLICY_HOLDER_ID,
    POLICY_TYPE,
    PREMIUM_AMOUNT,
    STATUS
FROM
    PREMIERINSURERS.POLICIES
WHERE
    STATUS = 'Active' AND POLICY_TYPE = 'Auto'
LIMIT 5;