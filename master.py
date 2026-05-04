import pandas as pd

# Load your export

df = pd.read_csv('./Dataset/Master.csv')

# Save records with columns that have leading/trailing spaces in their names
original_columns = df.columns.tolist()
spacey_columns = [col for col in original_columns if col != col.strip()]
if spacey_columns:
	df[spacey_columns].to_csv('./Dataset/columns_with_spaces.csv', index=False)

# Clean column names for further processing
df.columns = df.columns.str.strip()

# Create a unique ID that uses Contact ID if Lead ID is null (the conversion bridge)
df['Unified_ID'] = df['mm_Lead__c'].fillna(df['mm_Contact__c'])

# Group by the person and get a set of their stages
stages_per_person = df.groupby('Unified_ID')['mm_Stage__c'].apply(set)

# Filter for those who have MQL but NOT SAL
bucket_1 = stages_per_person[stages_per_person.apply(lambda x: 'MQL' in x and 'SAL' not in x)]

# Save bucket_1 records to CSV
bucket_1_ids = bucket_1.index.tolist()
df[df['Unified_ID'].isin(bucket_1_ids)].to_csv('./Dataset/bucket_1_records.csv', index=False)
print(f"Total records needing SAL backfill: {len(bucket_1)} (saved to ./Dataset/bucket_1_records.csv)")

# Filter for those who have SAL but NOT MQL
bucket_2 = stages_per_person[stages_per_person.apply(lambda x: 'SAL' in x and 'MQL' not in x)]

# Save bucket_2 records to CSV
bucket_2_ids = bucket_2.index.tolist()
df[df['Unified_ID'].isin(bucket_2_ids)].to_csv('./Dataset/bucket_2_records.csv', index=False)
print(f"Total records needing MQL backfill (Outbound/Cold Calls): {len(bucket_2)} (saved to ./Dataset/bucket_2_records.csv)")

# Save healthy dataset (not in bucket_1 or bucket_2)
unhealthy_ids = set(bucket_1_ids) | set(bucket_2_ids)
healthy_df = df[~df['Unified_ID'].isin(unhealthy_ids)]
healthy_df.to_csv('./Dataset/healthy_records.csv', index=False)
print(f"Total healthy records: {len(healthy_df)} (saved to ./Dataset/healthy_records.csv)")