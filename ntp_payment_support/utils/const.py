import re
import hashlib

if False:
    # TODO: stupid to remove this implementation
    PUID_PREFIX = "puid"
    PUID_REGEX = "puid[a-fA-F0-9]{8}"

    def hash_content_to_puid(content):
        puid = ""
        if content:
            puid = PUID_PREFIX + hashlib.sha1(content.encode()).hexdigest()[:8]
        return puid


    def extract_puid_from_content(content):
        if not content:
            return []
        matched = re.findall(PUID_REGEX, content, re.IGNORECASE)
else:
    # the most stupid solution that have ever done
    PUID_PREFIX = "BNK"
    PUID_REGEX = "BNK\d+\S+\d+|CSH\d+\S+\d+"

    # record: payment
    def hash_content_to_puid(record, content):
        puid = ""
        if content:
            if record.state != 'draft':
                puid = record.name
        return puid

    # record: bank statement line
    def extract_puid_from_content(record, content):
        journal_prefix = ["CSH", 'BNK']
        delimiter = ".." if '..' in content else '|'
        if not content:
            return []
        matched = []
        for part in content.split(delimiter):
            matched += re.findall(PUID_REGEX, part, re.IGNORECASE)
        return matched
