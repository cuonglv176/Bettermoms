import re
import sys
from jinja2 import Template

sys.path.insert(0, "/home/duychu/work15/odoo")

from pathlib import Path
import pandas as pd

headers = [
    "citad_code",
    "citad_bank_branch",
    "bank_name",
    "region_name",
    "cfm_bank_name",
    "bank_short_name",
]
data = pd.read_excel(
    "VN_BANK_CODE_2022May12_SHINHAN.xlsx",
)
data.columns = headers
bank_branches = data.to_dict(orient="records")

convert_ = {"<": "&lt;", ">": "&gt;", '"': "&quot;", "&": "&amp;", "'": "&apos;"}


def get_ref_bank(short_name):
    return re.sub("[^a-zA-Z0-9]", "_", short_name).lower()


for _id in range(len(bank_branches)):
    for esc in convert_:
        for name in headers:
            if type(bank_branches[_id][name]) != str:
                continue
            if esc in bank_branches[_id][name]:
                bank_branches[_id][name] = bank_branches[_id][name].replace(
                    esc, convert_[esc]
                )
    bank_branches[_id]["bank_short_name"] = re.sub(
        "\s+", " ", bank_branches[_id]["bank_short_name"]
    )
    bank_branches[_id]["bank_name"] = re.sub(
        "\s+", " ", bank_branches[_id]["bank_name"]
    )
    bank_branches[_id]["bank_ref"] = get_ref_bank(bank_branches[_id]["bank_name"])
    bank_branches[_id]["region_name"] = bank_branches[_id]["region_name"].title()
    if 'Ho Chi Minh' in bank_branches[_id]["region_name"]:
        bank_branches[_id]["region_name"] = 'Ho Chi Minh'


banks = []


def is_bank_in_list(bank_list, bank_name):
    for bank in bank_list:
        if bank["bank_name"] == bank_name:
            return True
    return False


for branch in bank_branches:
    if not is_bank_in_list(banks, branch["bank_name"]):
        banks.append(
            {
                "bank_name": branch["bank_name"],
                "bank_short_name": branch["bank_short_name"],
                "bank_ref": get_ref_bank(branch["bank_name"]),
            }
        )

with open("template.j2.xml") as f:
    tmpl = Template(f.read())

data_xml = tmpl.render(bank_items=banks, branch_items=bank_branches)

with open("data.xml", "w") as f:
    f.write(data_xml)
