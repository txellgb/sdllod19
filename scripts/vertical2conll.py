#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Converts a vertical file taken from the Komodo corpus to Json.
TODO:
    add an option to run validation on the output

How to run it:
vertical2json.py --input <input folder|input file> --out_dir <output_folder>

It takes two parameters:
* input: it can be either a file or a folder. If it is a folder the script will read all files in the folder.
* out_dir: the output folder where to store the Json files.

The script creates 5 different files for each document extracted from the vertical file:
document, datalayer, terminals, tokens and sentences.
Each filename has the following patterns:
```<input_filename>.<doc_id>.<file_type>.json``` where file_type is one of the above types of output files,
and the doc_id is extracted from the vertical file (see below).

Input vertical files have the format shown below. They can contain more than one document, each having several sentences.
Every token of a sentence is in a separate line.
Each line has 5 columns: word, token, lemma, PoS and lemma-PoS
Note that komodo vertical files are already tokenized, hence words and tokens are the same string.
```
<doc
   title="..."
   url="..."
   genre="..."
   domain="..."
   country="..."
   city="..."
   content_source="..."
   document_source="...."
   time_of_publication="..."
   month_of_publication="..."
   time_of_crawling="..."
   primary_doc_id="...">
    <s>
        word1   token1  lemma1  pos1
        word2   token2  lemma2  pos2
        word3   token3  lemma3  pos3
        ...
    </s>
    <s>
        word1   token1  lemma1  pos1
        word2   token2  lemma2  pos2
        word3   token3  lemma3  pos3
        ...
    </s>
    ...
</doc>
<doc ...
    <s>
        word1   token1  lemma1  pos1
        word2   token2  lemma2  pos2
        word3   token3  lemma3  pos3
        ...
    </s>
    ...
</doc>
```
"""

import io
from os import listdir,makedirs
from os.path import isfile, isdir, join, basename, dirname
import argparse
import xml.etree.ElementTree as ET
from copy import copy
import json


def dictify(r, root=True):
    """ converts an xml element to json """

    if root:
        return {r.tag : dictify(r, False)}
    d=copy(r.attrib)
    if r.text:
        d["_text"]=r.text
    for x in r.findall("./*"):
        if x.tag not in d:
            d[x.tag]=[]
        d[x.tag].append(dictify(x,False))
    return d


def process_document(document):
    """ takes an xml element with document information and converts it to the json
    metadata structure defined for the corpus data model. It also returns the doc_id """

    document = document.strip().replace(document[len(document)-2], '/>')
    document = document.replace("&", "&amp;")

    try:
        doc = ET.fromstring(document)
        json_doc = dictify(doc)
        doc_id = json_doc["doc"]["primary_doc_id"]
        metadata = {
            "title": json_doc["doc"]["title"] if json_doc["doc"]["title"] else "",
            "sourceUrl": json_doc["doc"]["url"] if json_doc["doc"]["url"] else "",
            "documentSource": json_doc["doc"]["document_source"] if json_doc["doc"]["document_source"] else "",
            "language": "en",
            "script": "lat",
            "datePublished": json_doc["doc"]["time_of_publication"] if json_doc["doc"]["time_of_publication"] else "",
            "monthPublished": json_doc["doc"]["month_of_publication"] if json_doc["doc"]["month_of_publication"] else "",
            "labels": [],
            "contentSource": json_doc["doc"]["content_source"] if json_doc["doc"]["content_source"] else "",
            "dateDownloaded": json_doc["doc"]["time_of_crawling"] if json_doc["doc"]["time_of_crawling"] else "",
            "dateIngested": ""
        }
    except ET.ParseError as ex:
        print("Error in the following document: ", document, ex)
        return None, None
    return doc_id, metadata


def read_document(f_in):
    conll_document = None

    for line in f_in:
        if line.startswith("<doc "):
            conll_document = []
            doc_id, _ = process_document(line)
            conll_document.append("# " + line)
        elif line.startswith("<s>") and doc_id is not None:
            continue
        elif line.startswith("</s>") and doc_id is not None:
            conll_document.append("\n")
        elif line.startswith("</doc>") and doc_id is not None:
            yield doc_id, conll_document
        elif doc_id is not None:
            conll_document.append(line)


def write_document(segments, f_conll):
    for item in segments:
        f_conll.write("%s" % item)


if __name__ == '__main__':
    """ if the input parameter is a folder, reads all the files in the folder and process them to extract the 
    text information. 5 output files are created for every document in the vertical files. Note that every 
    vertical file can contain more than one document. """
    parser = argparse.ArgumentParser(description='Reads input file in vertical format and outputs a collection of json files')
    parser.add_argument("--input", help="input filename")
    parser.add_argument("--out_dir", help="output folder")
    args = parser.parse_args()

    print('Reading from:', args.input)
    print('Writing to:', args.out_dir)
    makedirs(args.out_dir, exist_ok=True)

    filenames_list = []
    # determine if the input is a file or a folder
    if isdir(args.input):
        filenames_list = [[args.input, f] for f in listdir(args.input) if isfile(join(args.input, f))]
    elif isfile(args.input):
        f = basename(args.input)
        folder = dirname(args.input)
        filenames_list = [[folder, f]]

    for d, f in filenames_list:
        # open input file
        f_input = io.open(join(d, f), mode="r", encoding="utf-8")
        print('Reading :', join(d, f))
        my_document_reader = read_document(f_input)
        for doc_id, segments in my_document_reader:
            # open output files
            output_file = join(args.out_dir, doc_id)
            f_conll_rdf = io.open(output_file + ".conll", mode="w", encoding="utf-8")
            write_document(segments, f_conll_rdf)
            # close all files
            f_conll_rdf.close()
            print("Wrote files with prefix", output_file)
        f_input.close()
