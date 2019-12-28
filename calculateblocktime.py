import math
import datetime

chainstartdate = 1576264417
nowtime = int(datetime.datetime.now().strftime("%s"))

chaintime=nowtime-chainstartdate

slot = int(math.floor((chaintime % 86400) / 2))
epoch = int(math.floor(chaintime/ 86400))

blocktime=str(epoch)+"."+str(slot)

print "\n\n",blocktime

