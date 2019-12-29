import subprocess

jclistringinit = 'jcli rest v0 account get '
jclistringend = ' -h http://127.0.0.1:3100/api | grep "reward:" '
account="x"

while account != 0:

    account = raw_input("Enter account or public key:")

    jclistring = jclistringinit + account + jclistringend

    print(jclistring)

    rewardstring=subprocess.check_output(jclistring, shell=True)

    rewardstring=float(rewardstring[10:])/1000000
    print rewardstring, "ADA"
