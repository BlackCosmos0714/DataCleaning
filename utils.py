import pandas as pd

sht = pd.read_csv('./Dataset/SHT.csv')
sht.columns = sht.columns.str.strip()

# Exclude rows where both mm_Lead__c and mm_Contact__c are empty
sht = sht[sht['mm_Lead__c'].notna() | sht['mm_Contact__c'].notna()]

sht.to_csv('./Dataset/SHT_clean.csv', index=False)
print(f"Rows removed:    {293895 - len(sht)}")
print(f"Rows remaining:  {len(sht)}")

df = pd.read_csv('e:/Intradiem/DataCleaning/Dataset/group1_sal_backfill_enriched.csv')
unresolved = df[df['SAL_end_date'].isna()]
print(f'Total unresolved: {len(unresolved)}')
print()
print(unresolved[['canonical_id', 'id_type', 'Name', 'MQL_start_date', 'SAL_date_source']].to_string(index=False))

# Save them to a file
unresolved.to_csv('e:/Intradiem/DataCleaning/Dataset/group1_unresolved_sal_end_date.csv', index=False)
print()
print('Saved to: ./Dataset/group1_unresolved_sal_end_date.csv')