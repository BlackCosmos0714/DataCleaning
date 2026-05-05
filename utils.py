import pandas as pd

sht = pd.read_csv('./Dataset/SHT.csv')
sht.columns = sht.columns.str.strip()

# Exclude rows where both mm_Lead__c and mm_Contact__c are empty
sht = sht[sht['mm_Lead__c'].notna() | sht['mm_Contact__c'].notna()]

sht.to_csv('./Dataset/SHT_clean.csv', index=False)
print(f"Rows removed:    {293895 - len(sht)}")
print(f"Rows remaining:  {len(sht)}")
