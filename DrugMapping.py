import pandas as pd
import re
import requests

# === load medication dataset ===
df = pd.read_csv("Medications_v5.csv", low_memory=False)
# print(df.iloc[4:9, 1])

# clean and normalize drug names
def normalize_drug_name(name):
    name = str(name).lower()
    # print(name)
    # remove unwanted words
    name = re.sub(r'\b(product|oral|tablet|tablets|pill|tab|ointment|drops|eye drops|syrup|powder|patch|'
                  r'capsule|capsules|syringe|caplet|injection|and|liquid|solution|gel|softgel)\b', ' ', name)

    name = re.sub(r'\d+(\.\d+)?\s*(mg|ml|mcg|g|iu|U)?'
                  r'(/\s*(\d+)?(\.\d+)?\s*(mg|ml|mcg|g|iu|U))?', ' ', name)  # remove dosage
    name = re.sub(r'[^\w\s]', ' ', name)  # remove_punctuations
    name = re.sub(r'\s+', ' ', name)
    return name.strip()

df['normalized_drug'] = df['DRUGNAME'].apply(normalize_drug_name)
# df[['DRUGNAME', 'normalized_drug']].to_csv('DrugList_dataset.csv', index=False)


# === Identify antiHTN drug members using RxCUI based on ATC ===
def get_drug_members_by_class(atc_class_id):
    url = "https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json"
    params = {"classId": atc_class_id, "relaSource": "ATC"}

    response = requests.get(url, params=params)
    data = response.json()
    # print(data)

    members = data.get('drugMemberGroup', {}).get('drugMember', {})
    ingredientList = []

    for member in members:
        min_concept = member.get("minConcept", {})
        name = min_concept.get("name")
        ingredientList.append(name)

    # print(ingredientList)
    return ingredientList

## create the name list
all_names = set()
atc_classes = ['C02', 'C03', 'C07', 'C08', 'C09']  # ATC codes for antihypertensives
# atc_classes = ['C08']
for class_id in atc_classes:
    print(f"Fetching drugs from ATC: {class_id}")
    class_names = get_drug_members_by_class(class_id)
    all_names.update(class_names)
    # print(all_names)
# flat_names = all_names[0]
# print(flat_names)
# print(all_names)
ingredient_set = set()

for name in all_names:
    # print(name)
    # print('-----')
#     name = name.lower().strip()
#     # print('b')
    name = name.replace("/", ",")
    ingredients = [part.strip() for part in name.split(",") if part.strip()]
    ingredient_set.update(ingredients)
#     # print(ingredient_set)
#
ingredients_sorted = sorted(ingredient_set)
# print("!!")
# print(ingredients_sorted)
# output_file = "ATC_Dictionary.csv"
# pd.DataFrame(ingredients_sorted, columns=["Ingredients"]).to_csv(output_file,index=False)

# df_dict = pd.DataFrame(unique_drugs, columns=["RxCUI", "DrugName"])
# df_dict.to_csv("antihypertensive_dictionary.csv", index=False)

# === Map the ingredient list to associated brand name ===
# === From ATC to all possible names (brand, generic etc)

# get RxCUI for each ingredient name
def get_rxcui(name):
    url = "https://rxnav.nlm.nih.gov/REST/rxcui.json"
    params = {"name": name, "search": 2}
    r = requests.get(url, params=params)
    data = r.json()
    return data.get("idGroup", {}).get("rxnormId", [None])[0]

def get_synonyms(rxcui):
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/allProperties.json"
    params = {"prop": "names"}
    r = requests.get(url, params=params)
    data = r.json()
    synonyms = set()
    for prop in data.get("propConceptGroup", {}).get("propConcept", []):
        synonym = prop["propValue"]
        # print(type(synonym))
        synonyms.add(synonym.lower())
    return synonyms

def get_brand_name(rxcui):
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/related.json"
    params = {"tty": "BN"}
    r = requests.get(url, params=params)
    data = r.json()

    brands = set()
    for group in data.get("relatedGroup", {}).get("conceptGroup", []):
        for concept in group.get("conceptProperties", []):
            name1 = concept.get("name")
            brands.add(name1.lower())
    return brands

def build_clean_mapping(ingredient_list):
    all_names = set()
    for name in ingredient_list:
        # print(name)
        rxcui = get_rxcui((name))
        if not rxcui:
            print(f" No RxCUI found for {name}")
            continue
        all_names.add(name)
        synonyms = get_synonyms(rxcui)
        all_names.update(synonyms)
        brands = get_brand_name(rxcui)
        all_names.update(brands)


    return sorted(all_names)


completeRxList = build_clean_mapping(ingredients_sorted)
# print(a)
pd.DataFrame(completeRxList).to_csv("antiHTN_drugList.csv",index=False)









