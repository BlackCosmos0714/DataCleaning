import pandas as pd

# ── Load data ──────────────────────────────────────────────────────────────
sht = pd.read_csv('./Dataset/sht_raw.csv')
leads_sql = pd.read_csv('./Dataset/leads_sql_raw.csv')

sht.columns = sht.columns.str.strip()
leads_sql.columns = leads_sql.columns.str.strip()

sht['mm_Lead__c'] = sht['mm_Lead__c'].str.strip().replace('', pd.NA)
sht['mm_Contact__c'] = sht['mm_Contact__c'].str.strip().replace('', pd.NA)
sht['mm_Stage__c'] = sht['mm_Stage__c'].str.strip()

sht = sht.dropna(subset=['mm_Lead__c', 'mm_Contact__c'], how='all')

# ── Build Lead → Contact conversion map ───────────────────────────────────
converted = leads_sql[
    leads_sql['IsConverted'].astype(str).str.lower() == 'true'
][['Id', 'ConvertedContactId']].dropna()

lead_to_contact = dict(zip(
    converted['Id'].str.strip(),
    converted['ConvertedContactId'].str.strip()
))

# ── Assign canonical ID ────────────────────────────────────────────────────
# Converted leads → Contact ID (backfill targets the Contact)
# Non-converted leads → Lead ID
# Contact-only records → Contact ID

def get_canonical_id(row):
    lead_id = row['mm_Lead__c']
    contact_id = row['mm_Contact__c']
    if pd.notna(lead_id):
        return lead_to_contact.get(lead_id, lead_id)
    return contact_id

sht['canonical_id'] = sht.apply(get_canonical_id, axis=1)

# ── Stage sets per person ──────────────────────────────────────────────────
stages = sht.groupby('canonical_id')['mm_Stage__c'].apply(set)

# ── SQL person set ─────────────────────────────────────────────────────────
# Source 1: SQL stage present in SHT
sql_from_sht = set(stages[stages.apply(lambda x: 'SQL' in x)].index)

# Source 2: Lead.Status export (safety net for leads with no SHT entries)
def lead_canonical_id(row):
    lead_id = str(row['Id']).strip()
    if str(row.get('IsConverted', '')).lower() == 'true':
        contact_id = row.get('ConvertedContactId')
        if pd.notna(contact_id):
            return str(contact_id).strip()
    return lead_id

leads_sql['canonical_id'] = leads_sql.apply(lead_canonical_id, axis=1)
sql_from_leads = set(leads_sql['canonical_id'])

all_sql = sql_from_sht | sql_from_leads

# ── Group 1: SQL + MQL + no SAL → SAL backfill ────────────────────────────
group1 = {
    cid for cid, s in stages.items()
    if 'MQL' in s and 'SAL' not in s and cid in all_sql
}

# ── Group 2: SAL + no MQL → MQL backfill ──────────────────────────────────
group2 = {
    cid for cid, s in stages.items()
    if 'SAL' in s and 'MQL' not in s
}

# ── Group 3: SQL + no MQL + no SAL → investigate ──────────────────────────
# From SHT: SQL stage present but MQL and SAL absent
group3_in_sht = {
    cid for cid, s in stages.items()
    if 'SQL' in s and 'MQL' not in s and 'SAL' not in s
}

# Safety net: SQL leads that have no SHT entries at all
group3_no_sht = all_sql - set(stages.index)

group3 = group3_in_sht | group3_no_sht

# ── Save outputs ───────────────────────────────────────────────────────────
def save_group(ids, label, filename):
    df = pd.DataFrame({'canonical_id': sorted(ids), 'group': label})
    df.to_csv(f'./Dataset/{filename}', index=False)
    print(f"{label}: {len(ids):>4} records  →  {filename}")

save_group(group1, 'Group 1 - SAL Backfill',   'group1_sal_backfill.csv')
save_group(group2, 'Group 2 - MQL Backfill',   'group2_mql_backfill.csv')
save_group(group3, 'Group 3 - Investigate',    'group3_investigate.csv')
