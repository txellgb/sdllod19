#!/bin/bash

# HOME=`echo $0 | sed -e s/'^[^\/]*$'/'.'/g -e s/'\/[^\/]*$'//`;
# ROOT=$HOME/../../conll-rdf/;
# DATA=$ROOT/data;
# SPARQL=$ROOT/examples/sparql;

HOME=`pwd`
INDATA=../datasets/oup/out
OUTDATA=../datasets/oup/conll-rdf
RUNPATH=../../conll-rdf

echo $RUNPATH
cd $RUNPATH

# 1. read
for file in $HOME/$INDATA/*; do 
    echo "file is: " $file;
    filename=$(basename -- "$file")
    extension="${filename##*.}"
    doc_id="${filename%.*}"
	
	cat $file | \
    # 2. parse UD data to RDF
    ./run.sh \
	CoNLLStreamExtractor https://github.com/txellgb/sdllod19/datasets/oup/conll-rdf/$doc_id# \
	WORD TOKEN LEMMA POS LEMPOS | \
	\
	# 3. format
	./run.sh CoNLLRDFFormatter -rdf WORD TOKEN LEMMA POS LEMPOS $* > $HOME/$OUTDATA/$doc_id.ttl 
	
done
cd $HOME
