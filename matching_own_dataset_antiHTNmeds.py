## further refine the reference mapping table

## the reference is based on RxNorm database (US based), so some medications in our own dataset (AU brand) may not be
## found in RxNorm.

# generally, this file is to generate a final version of the mapping table, apart from RxNorm databaset,
# 1) I performed an initial filtering on own our own dataset - to remove non-tablet drug and vitamins.
# 2) Based on the previously obtained reference mapping table, I implemented it on our own dataset using the drug keyword,
# to do the matching.
# 3) realize there are some antiHTN drug  which are not found in the reference mapping table. So have manually expanded as those are
# not available in RxNorm dataset. so have performed some manual addition
# --> created a final version of reference mapping table ("mapped_antiHTN_unique.csv")
# 4) using the attached "mapped_antiHTN_unique.csv" (reference mapping table), to identify antiHTN medication
# in our own dataset and remove those without antiHTN drugs. --> matched_dataset.csv

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
    # === load our own medication dataset ===
    df = pd.read_csv("Medications_v5.csv", low_memory=False)
    # print(df.iloc[4:9, 1])
    drug_name = str(df['DRUGNAME']).lower()

    # == initial filtering - remove all confirmed non-antiHTN drug==
    drop_form = ("injection", "solution", "suspension", "ointment", "drops", "eye drops", "syrup", "syringe", "powder", "patch", "liquid",
                "gel", "cream", "pessaries", "pessary", "suppository", "sachet", "sinus", "lotion", "telfast", "zytrec", "panadol", "paracetamol",
                 "neo-b12", "eye/ear", "cough", "modified release", "vitamin", "blackmores", "vaginal", "transdermal", "suppositories", "fish oil",
                 "melatonin", "mersyndol", "aspirin", "ampoule", "demazin", "glucose")
    pattern = "|".join(drop_form)
    df = df[~df['DRUGNAME'].str.lower().str.contains(pattern, na=False)] # initial filtered dataset

    # == normalize
    df['normalized_drug'] = df['DRUGNAME'].apply(normalize_drug_name)
    # df_kept[['Patient_UUID','DRUGNAME', 'DOSE', 'PrescribedDate', 'Frequency','Strenght', 'Repeats','Quantity',
    #          'normalized_drug']].to_csv('filtered_list.csv', index=False)


    # == load the antiHTN_drug_dictionary and normalize the drug name [all lower caps and remove numbers] ==
    # reference drug list NORMALIZATION
    drug_dict = pd.read_csv('antiHTN_drug_filtered_MAPPING.csv', low_memory=False)
    norm_drug = drug_dict['name'].apply(normalize_drug_name)

    drug_dict['norm_drug'] = norm_drug
    # drug_dict.to_csv('antiHTN_drug_filtered_MAPPING_norm.csv', index=False)

    # == From 'antiHTN_drug_filtered_MAPPING_norm.csv', manual identification was performed to double-check the normalization
    # and further removed the confirmed non-used antiHTN medication from the reference list. --> the table was then
    # saved to 'Normalized_reference_drug_table.csv' ==

    # --------------------------------------------------------------------------------------------------------------- #

    reference_drug_table = pd.read_csv('Normalized_reference_drug_table.csv', low_memory=False)
    norm_drug = reference_drug_table['norm_drug']
    # print(norm_drug)
    # match the dictionary with own dataset to identify the target drug

    ref_token = set()
    for ref in norm_drug:
        a = set(ref.split())
        # print(a)
        ref_token.update(a)
    # pprint(len(ref_token))

    # == identified antiHTN drug in our own dataset ==
    pattern1 = r"\b(?:" + "|".join(ref_token) + r")\b"
    # pprint(pattern1)

    df["is_antiHTN"] = df['normalized_drug'].str.contains(pattern1, regex=True)  # return true or false
    df["match_token"] = df['normalized_drug'].str.findall(pattern1)

    df_isDRUG = df[df['is_antiHTN']]

    ignore_LIST = ("travoprost timolol", "dorzolamide timolol", "latanoprost timolol", # these are for ocular hypertension
                   "sacubitril valsartan", # heart failure
                   "nimodipine", # prevent vasospasm secondary to subarachnoid hemorrhage.
                   "cartia", # in AU, this is a low-dose aspirin
                   "lasix") # Lasix and Lasix M are mainly for edema
    ignore_pattern = r"\b(?:" + "|".join(ignore_LIST) + r")\b"

    df_isDRUG = df_isDRUG[~df_isDRUG['normalized_drug'].astype(str).str.contains(ignore_pattern, regex=True)] # drop
    # print(len(df_isDRUG))

    #----------------------------------------------------------------------------------------------------------------#

    drug_unique = df_isDRUG['normalized_drug'].unique() # from our own dataset
    # print(type(b))
    # pd.DataFrame(b, columns=['drug']).to_csv("unique_list.csv", index=False)
    # from this unique list --> identify which is not meant for antiHTN purposes

    # to map each identified antiHTN drug from the unique list into its class and regimen
    keep_drug = []
    unmatched = []

    ref_key = set(reference_drug_table['norm_drug'])
    print(ref_key)

    for drug_NAME in drug_unique:
        if drug_NAME in ref_key:
            # print(drug_NAME)
            # get the matching row
            ref_drug_row = reference_drug_table.loc[reference_drug_table["norm_drug"] == drug_NAME].iloc[0]
            # print(ref_drug_row)
            keep_drug.append({
                "drug": drug_NAME,
                "ingredient": ref_drug_row['ingredient'],
                "drugClass": ref_drug_row['drugClass'],
                "regimen": ref_drug_row['regimen']
            })
        else:
            unmatched.append({
                "drug": drug_NAME,
                "ingredient": "",
                "drugClass": "",
                "regimen": ""
            })

        cols = ["drug", "ingredient", "drugClass", "regimen"]
        df_keep = pd.DataFrame(keep_drug, columns=cols)
        df_unm = pd.DataFrame(unmatched, columns=cols)

        out = pd.concat([df_keep, df_unm], ignore_index=True)

        # save
        # out.to_csv("mapped_antiHTN_unique.csv", index=False)

        ##____________________ FINAL STAGE _______________________##
        ref_mapping = pd.read_csv("mapped_antiHTN_unique.csv", low_memory=False)
        df_filtered = pd.read_csv("filtered_list.csv", low_memory=False) # own dataset after initial filtering

        dataset_norm_drug = df_filtered["normalized_drug"]
        ref_drug = ref_mapping["drug"]

        matched_dataset = (df_filtered.merge(ref_mapping, left_on=dataset_norm_drug, right_on=ref_drug,
                        how="inner", validate="m:1"))
        matched_dataset = matched_dataset.drop(columns=["drug"])
        matched_dataset.to_csv("matched_DATASET.csv", index=False)

        print("Drug matched: ", len(matched_dataset)) # 88422