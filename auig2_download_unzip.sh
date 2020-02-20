#!/bin/bash
set -e
if [[ $# -lt 1 ]]; then
    echo -e "Usage: $0 <orderid> <username> <password> <email_account_json> <auig2_credentials_json> <completed_id_json> " 1>&2
    echo -e "    - orderid: Order id from AUIG2"
    echo -e "    - username: Username for order id in AUIG2"
    echo -e "    - password: Password for order id in AUIG2"
    echo -e "    - email_account_json: json file with credentials of email account to send notifications Webdav server username"
    echo -e "    - auig2_credentials_json: json file with auig 2 accounts mapping to get pw for download"
    echo -e "    - completed_id_json: json file to track completed orderid downloads"
fi

module purge
module load python/3/intel/2020
python2 --version
python --version

EMAIL_SCRIPT='/home/stchin/alos2-scraper/send_email_and_update_list.py '
DOWNLOAD_SCRIPT='/home/stchin/alos2-scraper/auig2_download.py'

order=$1
username=$2
password=$3
email_account_json=$4
auig2_credentials_json=$5

if [[ -z $6 ]]; then
  completed_id_json=''
else
  completed_id_json=$6
fi

echo $@

if [[ -z $PBS_O_WORKDIR ]]; then
    cd $PBS_O_WORKDIR
fi

#send email to tell we are submitting download
msg="Download job ID in Gekko: $PBS_JOBID"
cmd="$EMAIL_SCRIPT -o $order -u $username -ea $email_account_json -a $auig2_credentials_json -cid '$completed_id_json' -mt submit -mo '$msg'"
echo $cmd
eval $cmd
echo "send complete"

# do the download
echo "Running Download Script from directory: $PBS_O_WORKDIR"
cmd="python3 $DOWNLOAD_SCRIPT -o $order -u $username -p $password"
echo $cmd
eval $cmd


#start to unzip
# DO NOT CHANGE THIS:
EXTRACTPATH="/home/data/INSAR/ALOS2"

file="${order}.zip"
# put the file in a temp directory and unzip
mkdir temp_$file
mv $file temp_$file/
cd temp_$file
unzip $file
# put the original zip file back where it was
mv $file ..

#determine the path and frame from the new, long-name zip file
file2=`ls 0*_*zip`
frame="F"${file2:28:4}
orbit=${file2:23:5}

#this emprical forumla to get path/track number is derived from Eric Lindsey's modeling
#path = mod( 14 * orbit + 24, 207 )
path=`echo $orbit |awk '{path=(14*$1+24)%207; printf("P%03d",path)}'`

# unzip a second time and delete the zip file
unzip $file2
rm -f $file2
mv summary.txt ${file2}.summary.txt

# move the unzipped data to the P/F folder
mkdir -p $extractpath/$path/$frame
mv * $extractpath/$path/$frame
cd ..
rm -rf temp_$file

#send email too say download and unzip is completed
msg="Download job ID in Gekko: $PBS_JOBID has completed. $file2 has been extracted into $extractpath/$path/$frame/"
cmd="$EMAIL_SCRIPT -o $order -u $username -ea $email_account_json -a $auig2_credentials_json -cid '$completed_id_json' -mt complete -mo '$msg'"
echo $cmd
eval $cmd

