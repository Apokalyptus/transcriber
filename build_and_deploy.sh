#!/bin/bash
declare -a tags=("registry.apokalyptus.duckdns.org/transcriber" "registry.apokalyptus.duckdns.org/transcriber:1.0" "registry.apokalyptus.duckdns.org/transcriber:latest")
rm log.txt
#docker login -u joern $HOST
docker build --no-cache --progress=plain . 2>&1 | tee log.txt
ID=`grep 'writing image' log.txt | awk '{print $4}'`
echo " ID:" $ID
for tag in "${tags[@]}"
do
	echo "TAG: $tag"  
	docker tag $ID $tag 
done 
docker push -a ${tags[0]} 
