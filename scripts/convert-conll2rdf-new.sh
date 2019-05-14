#!/bin/bash

DATA=../datasets/oup/out/;
OUTDATA=../datasets/oup/conll-rdf/;
RUN_PATH=../../conll-rdf/

# 1. read
for file in `find $DATA`; do \
    echo $file;
    filename=$(basename -- "$file")
    extension="${filename##*.}"
    doc_id="${filename%.*}"

    # 2. parse UD data to RDF
    $RUN_PATH/run.sh \
	CoNLLStreamExtractor https://github.com/txellgb/sdllod19/datasets/oup/conll-rdf/$doc_id# \
	ID WORD LEMMA POS LEMPOS | \
	\
	# 3. format
	$RUN_PATH/run.sh CoNLLRDFFormatter -rdf ID WORD LEMMA POS LEMPOS $* > $OUTDATA/$filename.ttl \
	    ; done
