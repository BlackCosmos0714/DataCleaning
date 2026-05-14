import pandas as pd
from difflib import get_close_matches
from datetime import timedelta

# ── Load inputs ────────────────────────────────────────────────────────────
group1 = pd.read_csv('./Dataset/group1_sal_backfill.csv')
group2 = pd.read_csv('./Dataset/group2_mql_backfill.csv')
leads_sql = pd.read_csv('./Dataset/leads_sql_raw.csv')
nate = pd.read_csv('./Dataset/Nate.csv')
sht = pd.read_csv('./Dataset/sht_raw.csv')
nate_xlsx = pd.read_excel('./Dataset/Nate meetings w. ID.xlsx')

# ── Clean SHT and resolve canonical_id ─────────────────────────────────────
sht.columns = sht.columns.str.strip()
sht['mm_Lead__c'] = sht['mm_Lead__c'].str.strip().replace('', pd.NA)
sht['mm_Contact__c'] = sht['mm_Contact__c'].str.strip().replace('', pd.NA)
sht['mm_Stage__c'] = sht['mm_Stage__c'].str.strip()
sht['mm_Start_Date__c'] = pd.to_datetime(sht['mm_Start_Date__c'], errors='coerce')
sht = sht.dropna(subset=['mm_Lead__c', 'mm_Contact__c'], how='all')

lead_to_contact = dict(zip(
    leads_sql[leads_sql['IsConverted'].astype(str).str.lower() == 'true']['Id'].str.strip(),
    leads_sql[leads_sql['IsConverted'].astype(str).str.lower() == 'true']['ConvertedContactId'].astype(str).str.strip()
))

def get_canonical_id(row):
    lead_id = row['mm_Lead__c']
    if pd.notna(lead_id):
        return lead_to_contact.get(lead_id, lead_id)
    return row['mm_Contact__c']

sht['canonical_id'] = sht.apply(get_canonical_id, axis=1)

# Stage start dates per person
mql_start = sht[sht['mm_Stage__c'] == 'MQL'].groupby('canonical_id')['mm_Start_Date__c'].min()
sal_start = sht[sht['mm_Stage__c'] == 'SAL'].groupby('canonical_id')['mm_Start_Date__c'].min()
sql_start = sht[sht['mm_Stage__c'] == 'SQL'].groupby('canonical_id')['mm_Start_Date__c'].min()

# ── Clean Nate's CSV (name-based, fallback) ────────────────────────────────
nate.columns = nate.columns.str.strip()
nate['Name'] = nate['Name'].str.strip()
nate['Meeting Complete'] = nate['Meeting Complete'].str.strip()
nate['Date of Meeting'] = nate['Date of Meeting'].str.strip()

nate_csv_completed = nate[nate['Meeting Complete'] == 'Yes'].dropna(subset=['Name']).copy()
nate_csv_completed['meeting_date'] = pd.to_datetime(
    nate_csv_completed['Date of Meeting'] + '-2025',
    format='%d-%b-%Y',
    errors='coerce'
)
name_to_meeting_date = dict(zip(nate_csv_completed['Name'], nate_csv_completed['meeting_date']))
nate_name_list = list(name_to_meeting_date.keys())

def find_meeting_date_by_name(name):
    if pd.isna(name):
        return None
    if name in name_to_meeting_date:
        return name_to_meeting_date[name]
    close = get_close_matches(name, nate_name_list, n=1, cutoff=0.85)
    return name_to_meeting_date[close[0]] if close else None

# ── Clean Nate's xlsx (ID-based, preferred) ────────────────────────────────
nate_xlsx.columns = nate_xlsx.columns.str.strip()
nate_xlsx['ID'] = nate_xlsx['ID'].astype(str).str.strip()
nate_xlsx['Meeting Complete'] = nate_xlsx['Meeting Complete'].astype(str).str.strip()
nate_xlsx['Date of Meeting'] = pd.to_datetime(nate_xlsx['Date of Meeting'], errors='coerce')
nate_xlsx['id_15'] = nate_xlsx['ID'].str[:15]

nate_xlsx_completed = nate_xlsx[nate_xlsx['Meeting Complete'] == 'Yes']
id_to_meeting_date_xlsx = (
    nate_xlsx_completed.dropna(subset=['Date of Meeting'])
                       .groupby('id_15')['Date of Meeting'].min()
                       .to_dict()
)

def find_meeting_date_by_id(canonical_id):
    return id_to_meeting_date_xlsx.get(str(canonical_id)[:15])

# ── Lookups from leads_sql_raw ─────────────────────────────────────────────
leads_sql['canonical_id'] = leads_sql.apply(
    lambda r: str(r['ConvertedContactId']).strip()
    if (str(r.get('IsConverted', '')).lower() == 'true'
        and pd.notna(r.get('ConvertedContactId')))
    else str(r['Id']).strip(),
    axis=1
)
leads_sql['mm_SQL_date__c'] = pd.to_datetime(leads_sql['mm_SQL_date__c'], errors='coerce')
id_to_name = dict(zip(leads_sql['canonical_id'], leads_sql['Name'].str.strip()))
id_to_sql_date_lead = dict(zip(leads_sql['canonical_id'], leads_sql['mm_SQL_date__c']))


# ── GROUP 1 — SAL backfill ────────────────────────────────────────────────
# Methodology (per Genna):
#   INSERT new SAL: Start = SAL_start_date, End = next stage start (SQL)
#   UPDATE existing MQL: End Date = SAL_start_date
group1['id_type'] = group1['canonical_id'].str[:3].map({'00Q': 'Lead', '003': 'Contact'})
group1['Name'] = group1['canonical_id'].map(id_to_name)
group1['MQL_start_date'] = group1['canonical_id'].map(mql_start)
# SQL anchor: prefer SHT SQL start_date, fall back to Lead.mm_SQL_date__c
group1['SQL_start_date'] = group1['canonical_id'].map(sql_start)
group1['SQL_start_date'] = group1['SQL_start_date'].fillna(
    group1['canonical_id'].map(id_to_sql_date_lead)
)
group1['nate_xlsx_date'] = group1['canonical_id'].apply(find_meeting_date_by_id)
group1['nate_name_date'] = group1['Name'].apply(find_meeting_date_by_name)


def pick_sal_start_date(row):
    """SAL Start Date is the date the meeting occurred (or our best guess)."""
    if pd.notna(row['nate_xlsx_date']):
        return row['nate_xlsx_date'], 'Nate xlsx (ID match)'
    if pd.notna(row['nate_name_date']):
        return row['nate_name_date'], 'Nate csv (name match)'
    if pd.notna(row['SQL_start_date']):
        return row['SQL_start_date'] - timedelta(days=1), 'SQL_start - 1'
    if pd.notna(row['MQL_start_date']):
        return row['MQL_start_date'] + timedelta(days=1), 'MQL_start + 1'
    return pd.NaT, 'unresolved'


picked_g1 = group1.apply(pick_sal_start_date, axis=1, result_type='expand')
group1['SAL_start_date'] = picked_g1[0]
group1['SAL_date_source'] = picked_g1[1]

# DemandTools fields
group1['SAL_end_date'] = group1['SQL_start_date']               # SAL ends when SQL begins
group1['MQL_end_date_update'] = group1['SAL_start_date']        # MQL now ends when SAL begins

group1[[
    'canonical_id', 'id_type', 'Name',
    'MQL_start_date', 'MQL_end_date_update',
    'SAL_start_date', 'SAL_end_date',
    'SQL_start_date', 'SAL_date_source'
]].to_csv('./Dataset/group1_sal_backfill_enriched.csv', index=False)


# ── GROUP 2 — MQL backfill ────────────────────────────────────────────────
# Methodology (per Genna):
#   INSERT new MQL: Start = SAL_start_date, End = SAL_start_date (zero duration)
group2['id_type'] = group2['canonical_id'].str[:3].map({'00Q': 'Lead', '003': 'Contact'})
group2['Name'] = group2['canonical_id'].map(id_to_name)
group2['SAL_start_date'] = group2['canonical_id'].map(sal_start)
group2['MQL_start_date'] = group2['SAL_start_date']
group2['MQL_end_date'] = group2['SAL_start_date']
group2['MQL_date_source'] = group2['SAL_start_date'].notna().map(
    {True: 'SAL_start_date (per Genna)', False: 'unresolved'}
)

group2[[
    'canonical_id', 'id_type', 'Name',
    'SAL_start_date', 'MQL_start_date', 'MQL_end_date',
    'MQL_date_source'
]].to_csv('./Dataset/group2_mql_backfill_enriched.csv', index=False)


# ── Summary ────────────────────────────────────────────────────────────────
print('── Group 1 (SAL Backfill) ─────────────────────────')
print(f'  Total records: {len(group1)}')
print('  SAL start date source:')
print(group1['SAL_date_source'].value_counts().to_string().replace('\n', '\n    '))
print(f'  Records with SAL_end_date resolved: {group1["SAL_end_date"].notna().sum()} / {len(group1)}')
print()
print('── Group 2 (MQL Backfill) ─────────────────────────')
print(f'  Total records: {len(group2)}')
print('  MQL date source:')
print(group2['MQL_date_source'].value_counts().to_string().replace('\n', '\n    '))
