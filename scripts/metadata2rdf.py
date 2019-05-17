#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
            "dc:title": json_doc["doc"]["title"] if json_doc["doc"]["title"] else "",
            "dcat:downloadURL": json_doc["doc"]["url"] if json_doc["doc"]["url"] else "",
            "dcterms:type": json_doc["doc"]["genre"] if json_doc["doc"]["genre"] else "",
            "dcterms:subject": json_doc["doc"]["domain"] if json_doc["doc"]["domain"] else "",
            "rdau:P60163": json_doc["doc"]["city"] + ", " + json_doc["doc"]["country"] if json_doc["doc"]["country"] and json_doc["doc"]["city"] else "",
            "dc:publisher": json_doc["doc"]["document_source"] if json_doc["doc"]["document_source"] else "",
            "dc:source": json_doc["doc"]["content_source"] if json_doc["doc"]["content_source"] else "",
            "dcterms:language": "en",
            "dcterms:issued": json_doc["doc"]["time_of_publication"] if json_doc["doc"]["time_of_publication"] else "",
            "dc:identifier": doc_id
        }
    except ET.ParseError as ex:
        print("Error in the following document: ", document, ex)
        return None, None
    return doc_id, metadata


def read_document(f_in):

    for line in f_in:
        if line.startswith("<doc "):
            doc_id, metadata = process_document(line)
        elif line.startswith("<s>") and doc_id is not None:
            continue
        elif line.startswith("</s>") and doc_id is not None:
            continue
        elif line.startswith("</doc>") and doc_id is not None:
            yield doc_id, metadata
        elif doc_id is not None:
            continue


def write_document_header(f_conll):
    prefixes = """@prefix rdau: <http://rdaregistry.info/Elements/u/> .
@prefix dc:     <http://purl.org/dc/elements/1.1/>
@prefix dcat:	<http://www.w3.org/ns/dcat#>
@prefix dcterms:	<http://purl.org/dc/terms/>
@prefix nif: <http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#> .
@prefix : <https://github.com/txellgb/sdllod19/datasets/oup/conll-rdf/> .
"""
    f_conll.write("%s" % prefixes)


def write_document_triples(doc_id, metadata, f_out):
    #mystr = "\n@prefix : <https://github.com/txellgb/sdllod19/datasets/oup/conll-rdf/> .\n"
    mystr = "\n:"+doc_id+" a :Document .\n"
    for key, value in metadata.items():
        mystr += ":"+doc_id+" "+key+" \""+value+"\" .\n"
    #mystr += "@prefix : <https://github.com/txellgb/sdllod19/datasets/oup/conll-rdf/"+doc_id+"#> .\n"
    mystr += ":" + doc_id + " nif:nextSentence :"+doc_id+"\#s1_0 .\n"
    f_out.write("%s" % mystr)


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
        # open output file
        f_conll_rdf = io.open(args.out_dir+ "/metadata.ttl", mode="w", encoding="utf-8")
        write_document_header(f_conll_rdf)
        for doc_id, metadata in my_document_reader:
            write_document_triples(doc_id, metadata, f_conll_rdf)
        # close all files
        f_conll_rdf.close()
        f_input.close()
