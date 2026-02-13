data = """
Incoming - ShinhanBank (Contact undefined) Message text: TK **0080 thanh toan the Ghi no  - VND 253,160. So du kha dung: VND 88,490,031.  . (**32) Purchase 30-06-2022. ODOO (7/5/22 6:45 PM)You received this letter because you set up SMS forwarding from your phone via the "SMS to phone / mail - auto redirect application" (https://play.google.com/store/apps/details?id=com.gawk.smsforwarder)If you don't want to receive such emails anymore - Unsubscribe

Incoming - ShinhanBank (Contact undefined) Message text: TK **0074 thay doi  - VND 1,333,308. So du kha dung: VND 404,360,886. CONG TY TNHH NIN SING LOGISTICS. ..default.v1.0..NTPTECH....BNK4/2022/07/0002..2022Jul..INV00000580 (7/6/22 11:34 AM)You received this letter because you set up SMS forwarding from your phone via the "SMS to phone / mail - auto redirect application" (https://play.google.com/store/apps/details?id=com.gawk.smsforwarder)If you don't want to receive such emails anymore - Unsubscribe

Incoming - ShinhanBank (Contact undefined) Message text: TK **0074 thay doi  - VND 8,615,640. So du kha dung: VND 405,705,194. CN CTY CP DV HH HK CON CA HEO TAI H. ..default.v1.0..NTPTECH....BNK4/2022/07/0007..2022Jul..INV00001600 (7/6/22 11:34 AM)You received this letter because you set up SMS forwarding from your phone via the "SMS to phone / mail - auto redirect application" (https://play.google.com/store/apps/details?id=com.gawk.smsforwarder)If you don't want to receive such emails anymore - Unsubscribe

Incoming - ShinhanBank (Contact undefined) Message text: TK **0080 thay doi  - VND 28,210,000. So du kha dung: VND 60,464,056. Cong ty Luat TNHH Quoc te ICT. ..default.v1.0..NTPTECH....BNK3/2022/07/0003..2022Jul..INV21..INV23 (7/6/22 11:35 AM)You received this letter because you set up SMS forwarding from your phone via the "SMS to phone / mail - auto redirect application" (https://play.google.com/store/apps/details?id=com.gawk.smsforwarder)If you don't want to receive such emails anymore - Unsubscribe

Incoming - ShinhanBank (Contact undefined) Message text: TK **0080 thay doi  - VND 1,404,000. So du kha dung: VND 46,399,896. CONG TY TNHH TELLUS TECH VINA. ..default.v1.0..NTPTECH....BNK3/2022/07/0001..2022Jul..INV00000155 (7/6/22 11:35 AM)You received this letter because you set up SMS forwarding from your phone via the "SMS to phone / mail - auto redirect application" (https://play.google.com/store/apps/details?id=com.gawk.smsforwarder)If you don't want to receive such emails anymore - Unsubscribe

Incoming - ShinhanBank (Contact undefined) Message text: TK **0080 thay doi  - VND 12,638,160. So du kha dung: VND 47,814,896. CONG TY TNHH MH GLOBAL LOGISTICS. ..default.v1.0..NTPTECH....BNK3/2022/07/0002..2022Jul..INV288 (7/6/22 11:35 AM)You received this letter because you set up SMS forwarding from your phone via the "SMS to phone / mail - auto redirect application" (https://play.google.com/store/apps/details?id=com.gawk.smsforwarder)If you don't want to receive such emails anymore - Unsubscribe
"""

# shinhan-vietnamese-smsforwarder
template = """
# Incoming - ShinhanBank (Contact undefined) Message text: TK **0080 thanh toan the Ghi no  - VND 253,160. So du kha dung: VND 88,490,031.  . (**32) Purchase 30-06-2022. ODOO (7/5/22 6:45 PM)You received this letter because you set up SMS forwarding from your phone via the "SMS to phone / mail - auto redirect application" (https://play.google.com/store/apps/details?id=com.gawk.smsforwarder)If you don't want to receive such emails anymore - Unsubscribe
Value Required ACCOUNT (\S+)
Value PAYMENT_TYPE ([\-+]|debit|credit)
Value AMOUNT ((\d+,?)+)
Value AMOUNT_CURRENCY ([A-Z]{3})
Value BALANCE ((\d+,?)+)
Value BALANCE_CURRENCY ([A-Z]{3})
Value MESSAGE (.+)
Value DATE (\d+/\d+/\d+ \d+:\d+ (AM|PM)?)


Start
  ^(.+)?Message text:(\s+)?TK(\s+)${ACCOUNT}\s+(thay doi|thanh toan the Ghi no)\s+${PAYMENT_TYPE}\s+${AMOUNT_CURRENCY}\s+${AMOUNT}\.(.+)So du kha dung:(\s+)${BALANCE_CURRENCY}\s+${BALANCE}\.(\s+)?${MESSAGE}\s+\(${DATE}\) -> Record

EOF
""".strip()


data2 = """

Message text: Acc no. **8468 credit VND 15,242,700. Available balance: VND 112,479,449. . VND-TGTT-VU THUY HOANG YEN;Baby boo boo FT22192259045010 (7/11/22 1:09 PM)


"""

template2 = """
# Message text: Acc no. **8468 credit VND 15,242,700. Available balance: VND 112,479,449. . VND-TGTT-VU THUY HOANG YEN;Baby boo boo FT22192259045010 (7/11/22 1:09 PM)
#from these notifications or sign in to manage your
#Email service.
Value Required ACCOUNT (\S+)
Value PAYMENT_TYPE ([\-+]|debit|credit)
Value AMOUNT ((\d+,?)+)
Value AMOUNT_CURRENCY ([A-Z]{3})
Value BALANCE ((\d+,?)+)
Value BALANCE_CURRENCY ([A-Z]{3})
Value MESSAGE (.+)
Value DATE (\d+/\d+/\d+ \d+:\d+ (AM|PM)?)


Start
  ^(.+)?Message text:(\s+)?Acc no\.(\s+)${ACCOUNT}\s+${PAYMENT_TYPE}\s+${AMOUNT_CURRENCY}\s+${AMOUNT}\.(.+)Available balance:(\s+)${BALANCE_CURRENCY}\s+${BALANCE}\.(\s+)?${MESSAGE}\s+\(${DATE}\) -> Record

EOF
""".strip()


from io import StringIO
from pandas import DataFrame
from textfsm import TextFSM
from tabulate import tabulate

parser = TextFSM(StringIO(template2))
parsed = parser.header, parser.ParseText(data2)
df = DataFrame(parsed[1], columns=parsed[0])
print(tabulate(df, headers="keys", tablefmt="psql"))