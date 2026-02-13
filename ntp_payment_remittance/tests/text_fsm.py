data = """
TK **0080 thay doi  - VND 990,000. So du kha dung: VND 118,737,599. CONG TY TNHH THUONG MAI VA DICH VU . NTP TECH TT TIEN KE TRUNG BAY SP..BILL/2022/01/0007 .NTP TECH PAY BRUSH MONSTER POP
From
January 28, 2022 at 09:34AM
via Android
Manage
Unsubscribe
from these notifications or sign in to manage your
Email service.

TK **0080 thay doi  - VND 3,914,499. So du kha dung: VND 114,813,200. CONG TY CO PHAN VINHOMES. CAN HO W13503 TT PHI DV T12 2021.PR/2021/12/0049 .W13503 PAY SERVICE FEE DEC 2021
From
January 28, 2022 at 09:35AM
via Android
Manage
Unsubscribe
from these notifications or sign in to manage your
Email service.

TK **0080 thay doi +  VND 73,437,293. So du kha dung: VND 149,590,658. CONG TY CO PHAN NTP-TECH. Internal transfer
From
February 07, 2022 at 03:21PM
via Android
Manage
Unsubscribe
from these notifications or sign in to manage your
Email service.

TK **0080 thanh toan the Ghi no  - VND 5,000,000. So du kha dung: VND 68,159,910.  . (**32) Purchase 27-01-2022. GOOGLE  ADS9192680391
From
February 08, 2022 at 06:48PM
via Android
Manage
Unsubscribe
from these notifications or sign in to manage your
Email service.

TK **0080 thay doi +  VND 139,336,000. So du kha dung: VND 310,087,744. TGIAN TTOAN GD THEO BKE CUA KH. //SAL2022046S049064821001//Cap tamung ODTS cho don vi 1 1 22 TE9214E
From
February 16, 2022 at 08:33AM
via Android
Manage
Unsubscribe
from these notifications or sign in to manage your
Email service.

Acc no. **8468 debit VND 15,175,650. Available balance: VND 52,110,727. CONG TY CO PHAN NTP-TECH. Sishibaby (15 Feb)
From
February 16, 2022 at 10:51AM
via Android
Manage
Unsubscribe
from these notifications or sign in to manage your
Email service.

TK **0080 thay doi  - VND 1,180,000. So du kha dung: VND 182,147,343. CONG TY CO PHAN CONG NGHE TIN HOC E. THANH TOAN DICH VU TE9214E- IC0329EMA 0108951191..BILL/2022/01/0004
From
February 14, 2022 at 07:05AM
via Android
Manage
Unsubscribe
from these notifications or sign in to manage your
Email service.

TK **0080 thay doi  - VND 6,393,600. So du kha dung: VND 175,743,843. CONG TY CO PHAN VDC. NTP TECH TT TIEN COC HOA DON 17. BILL/2022/02/0004.D-DAY CARD
From
February 15, 2022 at 02:41PM
via Android
Manage
Unsubscribe
from these notifications or sign in to manage your
Email service.
"""


template = """
# TK **0080 thay doi  - VND 990,000. So du kha dung: VND 118,737,599. CONG TY TNHH THUONG MAI VA DICH VU . NTP TECH TT TIEN KE TRUNG BAY SP..BILL/2022/01/0007 .NTP TECH PAY BRUSH MONSTER POP
# From
# January 28, 2022 at 09:34AM
# via Android
# Manage
# Unsubscribe
# from these notifications or sign in to manage your
# Email service.
Value Required ACCOUNT (\S+)
Value PAYMENT_TYPE ([\-+]|debit|credit)
Value AMOUNT ((\d+,?)+)
Value AMOUNT_CURRENCY ([A-Z]{3})
Value BALANCE ((\d+,?)+)
Value BALANCE_CURRENCY ([A-Z]{3})
Value MESSAGE (.+)
Value DATE ((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(.+))


Start
  ^(\s+)?TK(\s+)${ACCOUNT}\s+(thay doi|thanh toan the Ghi no)\s+${PAYMENT_TYPE}\s+${AMOUNT_CURRENCY}\s+${AMOUNT}\.(.+)So du kha dung:(\s+)${BALANCE_CURRENCY}\s+${BALANCE}\.(\s+)?${MESSAGE}
  ^(\s+)?${DATE}(\s+)? -> Record

EOF
""".strip()

template1 = """
# Acc no. **8468 debit VND 15,175,650. Available balance: VND 52,110,727. CONG TY CO PHAN NTP-TECH. Sishibaby (15 Feb)
# From
# February 16, 2022 at 10:51AM
# via Android
# Manage
# Unsubscribe
#from these notifications or sign in to manage your
#Email service.
Value Required ACCOUNT (\S+)
Value PAYMENT_TYPE ([\-+]|debit|credit)
Value AMOUNT ((\d+,?)+)
Value AMOUNT_CURRENCY ([A-Z]{3})
Value BALANCE ((\d+,?)+)
Value BALANCE_CURRENCY ([A-Z]{3})
Value MESSAGE (.+)
Value DATE ((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(.+))


Start
  ^(\s+)?Acc no\.(\s+)${ACCOUNT}\s+${PAYMENT_TYPE}\s+${AMOUNT_CURRENCY}\s+${AMOUNT}(.+)Available balance(.+)${BALANCE_CURRENCY}\s+${BALANCE}\.(\s+)?${MESSAGE}
  ^(\s+)?${DATE}(\s+)? -> Record

EOF
""".strip()

data2 = """
Transaction Approved PARK JONG HYUN(**40) 17-02-2022/19:17/857,000/KANG NAM MEON OK,Remaining Credit limit: 47,695,778
Transaction Approved PARK JONG HYUN(**40) 10-03-2022/15:23/33,000/Grab* A-36T5RXMWWFFH,Remaining Credit limit: 42,382,638
Transaction Approved PARK JONG HYUN(**40) 12-03-2022/17:47/249,392/Odoo,Remaining Credit limit: 42,102,246
Transaction Approved PARK JONG HYUN(**40) 23-02-2022/10:46/750,815/SO2022/1865027-2022022,Remaining Credit limit: 46,944,963
Transaction Approved PARK JONG HYUN(**40) 17-02-2022/19:17/857,000/KANG NAM MEON OK,Remaining Credit limit: 47,695,778
Transaction Approved PARK JONG HYUN(**27) 17-02-2022/13:50/113,000/Grab* A-346DT4VWWF3V,Available balance: 42,565,704(VND)
Transaction Approved PARK JONG HYUN(**27) 17-02-2022/13:50/113,000/Grab* A-346DT4VWWF3V,Available balance: 42,565,704(VND)
Transaction Approved PARK JONG HYUN(**40) 12-02-2022/19:19/773,280/CHA CHA CHA RESTAURANT,Remaining Credit limit: 48,552,778
Incoming - ShinhanBank (Contact undefined) Message text: Transaction Approved  PARK JONG HYUN(**40)  15-03-2022/19:24/679,320/CHA CHA CHA RESTAURANT,Remaining Credit limit: 41,416,442 (3/15/22 19:24)You received this letter because you set up SMS forwarding from your phone via the "SMS to phone / mail - auto redirect application" (https://play.google.com/store/apps/details?id=com.gawk.smsforwarder)If you don't want to receive such emails anymore - Unsubscribe
"""

template2 = """
Value Required ACCOUNT (.+(\s+)?\(\*\*\d+\))
Value PAYMENT_TYPE ([\-+]|debit|credit)
Value AMOUNT ((\d+,?)+)
Value AMOUNT_CURRENCY ([A-Z]{3})
Value BALANCE ((\d+,?)+)
Value BALANCE_CURRENCY ([A-Z]{3})
Value MESSAGE (.+)
Value DATE (\d{2}\-\d{2}\-\d{4}/\d{2}:\d{2})


Start
  ^(\s+|.+Message text:\s+)?Transaction Approved(\s+)?${ACCOUNT}(\s+)?${DATE}/${AMOUNT}/${MESSAGE},(Remaining Credit limit|Available balance):(\s+)?${BALANCE}(\s+)?(\(${BALANCE_CURRENCY}\)?)? -> Record

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