import pandas as pd

# ── Load MQL/SAL stage history ──────────────────────────────────────────────
df = pd.read_csv('./Dataset/Master.csv')
df.columns = df.columns.str.strip()
df['mm_Lead__c'] = df['mm_Lead__c'].str.strip().replace('', pd.NA)
df['mm_Contact__c'] = df['mm_Contact__c'].str.strip().replace('', pd.NA)
df['mm_Stage__c'] = df['mm_Stage__c'].str.strip()

# Drop rows where both IDs are absent
df = df.dropna(subset=['mm_Lead__c', 'mm_Contact__c'], how='all')

# Unified_ID: Lead ID takes priority, fall back to Contact ID
df['Unified_ID'] = df['mm_Lead__c'].fillna(df['mm_Contact__c'])
df['ID_Type'] = df['mm_Lead__c'].notna().map({True: 'Lead', False: 'Contact'})

# Stage sets per person
stages_per_person = df.groupby('Unified_ID')['mm_Stage__c'].apply(set)


# ── GROUP 2: SAL but no MQL → MQL backfill needed ───────────────────────────
# Reference SOQL (for validation against Lead records):
#   SELECT Id, Name, SALDate__c, mm_SQL_date__c, CreatedDate, LeadSource, CreatedBy.Name
#   FROM Lead
#   WHERE (Status = 'SAL' OR Status = 'SQL' OR Status = 'Qualified' OR Status = 'Customer' OR Status = 'Nurture')
#     AND Id IN     (SELECT mm_Lead__c FROM mm_Stage_History_Tracking__c WHERE mm_Stage__c = 'SAL')
#     AND Id NOT IN (SELECT mm_Lead__c FROM mm_Stage_History_Tracking__c WHERE mm_Stage__c = 'MQL')
#   ORDER BY CreatedDate DESC
group2_ids = stages_per_person[
    stages_per_person.apply(lambda x: 'SAL' in x and 'MQL' not in x)
].index.tolist()

group2_df = df[df['Unified_ID'].isin(group2_ids)].copy()
group2_df.to_csv('./Dataset/group2_sal_no_mql.csv', index=False)
print(f"Group 2 (SAL but no MQL)  → MQL backfill needed:       {len(group2_ids):>4} people")


# ── GROUP 3: SQL with no SAL and no MQL → flag for investigation ────────────
# Source: Bucket3.csv — pre-exported via SOQL:
#   SELECT Id, Name, mm_SQL_date__c, CreatedDate, LeadSource, CreatedBy.Name
#   FROM Lead
#   WHERE (Status = 'SQL' OR Status = 'Qualified' OR Status = 'Customer')
#     AND Id NOT IN (SELECT mm_Lead__c FROM mm_Stage_History_Tracking__c WHERE mm_Stage__c = 'MQL')
#     AND Id NOT IN (SELECT mm_Lead__c FROM mm_Stage_History_Tracking__c WHERE mm_Stage__c = 'SAL')
#   ORDER BY CreatedDate DESC

group3_df = pd.read_csv(
    './Dataset/Bucket3.csv',
    skiprows=2,
    header=None,
    names=['Lead_ID', 'Name', 'SQL_Date', 'Created_Date', 'Lead_Source', 'Created_By']
)
group3_df = group3_df.dropna(subset=['Lead_ID'])
group3_df['Lead_ID'] = group3_df['Lead_ID'].str.strip()
group3_df.to_csv('./Dataset/group3_sql_no_mql_no_sal.csv', index=False)
print(f"Group 3 (SQL, no MQL, no SAL) → flag for investigation: {len(group3_df):>4} records")


# ── GROUP 1: SQL + MQL but no SAL → SAL backfill needed ─────────────────────
# Groups 1 & 2 use Stage History as the source of truth (presence of events).
# Group 3 uses Lead directly (absence of events — SHT can't surface what never happened).
#
# Run this SOQL and save the result to ./Dataset/sql_mql_no_sal_leads.csv:
#
#   SELECT Id, Name, mm_MQL_date__c, mm_SQL_date__c, CreatedDate, LeadSource, CreatedBy.Name
#   FROM Lead
#   WHERE (Status = 'SQL' OR Status = 'Qualified' OR Status = 'Customer' OR Status = 'Nurture')
#     AND Id IN     (SELECT mm_Lead__c FROM mm_Stage_History_Tracking__c WHERE mm_Stage__c = 'MQL')
#     AND Id NOT IN (SELECT mm_Lead__c FROM mm_Stage_History_Tracking__c WHERE mm_Stage__c = 'SAL')
#   ORDER BY CreatedDate DESC

mql_no_sal_ids = set(
    stages_per_person[
        stages_per_person.apply(lambda x: 'MQL' in x and 'SAL' not in x)
    ].index
)

try:
    sql_mql = pd.read_csv('./Dataset/sql_mql_no_sal_leads.csv')
    sql_mql.columns = sql_mql.columns.str.strip()
    sql_lead_ids = set(sql_mql['Id'].str.strip())

    group1_ids = mql_no_sal_ids & sql_lead_ids
    group1_df = df[df['Unified_ID'].isin(group1_ids)].copy()
    group1_df.to_csv('./Dataset/group1_sql_mql_no_sal.csv', index=False)
    print(f"Group 1 (SQL + MQL, no SAL) → SAL backfill needed:    {len(group1_ids):>4} people")

except FileNotFoundError:
    print(
        "Group 1: sql_mql_no_sal_leads.csv not found.\n"
        "  Run the SOQL query above and save the result to ./Dataset/sql_mql_no_sal_leads.csv\n"
        f"  (MQL-but-no-SAL pool from SHT: {len(mql_no_sal_ids)} people pending SQL verification)"
    )
