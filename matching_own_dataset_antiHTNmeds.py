import pandas as pd
import re

# LOAD OWN ePBRN dataset

# clean and normalize drug names
def normalize_drug_name(name):
    name = str(name).lower()
    # print(name)
    name = re.sub(r'[^\w\s]', ' ', name)  # remove_punctuations
    # remove unwanted words
    name = re.sub(r'\b(product|oral|tablet|tablets|pill|tab|'
                  r'capsule|capsules|caplet|and|softgel|caplets|enteric coated|day|night)\b', ' ', name)
    name = re.sub(r'\d+(\.\d+)?\s*(mg|ml|mcg|g|iu|U)?'
                  r'(/\s*(\d+)?(\.\d+)?\s*(mg|ml|mcg|g|iu|U))?', ' ', name)  # remove dosage
    name = re.sub(r'\s+', ' ', name)
    return name.strip()

if __name__ == "__main__":
    # === load medication dataset ===
    df = pd.read_csv("Medications_v5.csv", low_memory=False)
    # print(df.iloc[4:9, 1])
    drug_name = str(df['DRUGNAME']).lower()

    drop_form = ("injection", "solution", "suspension", "ointment", "drops", "eye drops", "syrup", "syringe", "powder", "patch", "liquid",
                "gel", "cream", "pessaries", "pessary", "suppository", "sachet", "sinus", "lotion", "telfast", "zytrec", "panadol", "paracetamol",
                 "neo-b12", "eye/ear", "cough", "modified release", "vitamin", "blackmores", "vaginal", "transdermal", "suppositories", "fish oil",
                 "melatonin", "mersyndol", "aspirin", "ampoule", "demazin", "glucose")
    pattern = "|".join(drop_form)

    # == initial filtering - remove all confirmed non-antiHTN drug==
    df_kept = df[~df['DRUGNAME'].str.lower().str.contains(pattern, na=False)]
    # df_kept.to_csv('filtered_list.csv', index=False)

    # == normalize
    df_kept['normalized_drug'] = df_kept['DRUGNAME'].apply(normalize_drug_name)
    df_kept[['DRUGNAME', 'normalized_drug']].to_csv('filtered_list.csv', index=False)

    # == load the antiHTN_drug_dictionary and normalize the drug name [all lower caps and remove numbers] ==
    drug_dict = pd.read_csv('antiHTN_drug_filtered_MAPPING.csv', low_memory=False)
    norm_drug = drug_dict['name'].apply(normalize_drug_name)
    drug_dict['norm_drug'] = norm_drug
    drug_dict.to_csv('antiHTN_drug_filtered_MAPPING_norm.csv', index=False)

    ## match the dictionary with own dataset to identify the target drug





