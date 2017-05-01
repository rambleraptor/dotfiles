# Gcloud SSH
function gcloud-tunnel(){
  gcloud compute ssh $1 --ssh-flag="-L $2:localhost:$2"
}

function gssh() {
  gcloud compute ssh $1
}

function gcopy-home(){
  gcloud compute copy-files $1 $2:~
}

alias gcompute="gcloud compute"
alias gcp="gcloud compute copy-files $1 $2~"
