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


def create_terminals(list_of_words, start_idx):
    """ from an array of words it creates the json list that contains the same array of words.
    Note that the method adds a space " " terminal after each word. That's because we are generating
    the json from a vertical file where we only have tokens. Due the lack of the original source text,
    we assume each token is separated by a space, which is true in most cases but is not the case for
    symbols, punctuation marks etc.
    """
    terminals = []
    i = start_idx
    for word in list_of_words:
        terminals.append({"start": i, "end": i+len(word)+1, "string": word})
        i = i+len(word)+1
        terminals.append({"start": i, "end": i+1, "string": " "})
        i = i+1
    return terminals, i


def create_tokens(sentence, token_start):
    """ from a sentence dictionary having list of tokens, lemmas and pos, it creates a
    json list having the same information according to the corpus data model schema """
    tokens = []
    i = token_start
    for token, lemma, pos in zip(sentence["token"], sentence["lemma"], sentence["pos"]):
        tokens.append(
          {
            "relation": {
              "type": "tokenization",
              "references": [
                {"layer": 0, "node": i, "role": "tokenPart"}
              ]
            },
            "annotations": {"pos": {"tag": pos}, "lemma": lemma}
          },)
        i = i+2
    return tokens, i


def process_sentence(sentence, token_idx, terminal_idx, char_idx):
    """from a list of words that conforms a sentence, it creates a json dictionary having the
    segment information and the full text of the sentence, in addition to a json list of terminals
    and a json list of tokens according to the corpus data model schema."""
    data = " ".join(sentence["text"])
    terminals, char_idx = create_terminals(sentence["text"], char_idx)
    tokens, terminal_idx = create_tokens(sentence, terminal_idx)
    token_end = token_idx + len(tokens) + 1
    sentence = {
        "relation": {
          "type": "segment",
          "references": [
            {
              "layer": 0,
              "nodeRange": {"start": token_idx, "end": token_end - 1},
              "role": "part"
            }
          ]
        },
        "annotations": {
          "unit": "sentence"
        }
      }
    return data, terminals, tokens, sentence, token_end, terminal_idx, char_idx


def process_line(line):
    """splits a line of a vertical file to find out the elements it contains"""
    ar_line = line.strip().split("\t")
    return ar_line[0], ar_line[1], ar_line[2], ar_line[3]


def read_document(f_in):
    """ opens a vertical file and process it line by line """
    segments_list = doc = doc_id = None
    token_idx = terminal_idx = char_idx = 0
    for line in f_in:
        if line.startswith("<doc "):
            token_idx = terminal_idx = char_idx = 0
            doc_id, doc = process_document(line)
            segments_list = {"data": [], "terminals": [], "tokens": [], "sentences": []}
        elif line.startswith("<s>") and doc_id is not None:
            segment = {"text": [], "token": [], "lemma": [], "pos": [], "sentence": {}}
        elif line.startswith("</s>") and doc_id is not None:
            data, terminals, tokens, sentence, token_idx, terminal_idx, char_idx = process_sentence(segment, token_idx, terminal_idx, char_idx)
            segments_list["data"].append(data)
            segments_list["terminals"].extend(terminals)
            segments_list["tokens"].extend(tokens)
            segments_list["sentences"].append(sentence)
        elif line.startswith("</doc>") and doc_id is not None:
            yield doc_id, doc, segments_list
        elif doc_id is not None:
            word, token, lemma, pos = process_line(line)
            segment["text"].append(word)
            segment["token"].append(token)
            segment["lemma"].append(lemma)
            segment["pos"].append(pos)


def write_document(doc_id, doc, segments, f_datalayer, f_document, f_sentences, f_terminals, f_tokens):
    """takes the json data created for a document and writes the json files """
    document_json = {
        "$schema": "corpusDocument.schema.json",
        "id": doc_id+".doc",
        "metadata": doc
    }
    json.dump(document_json, f_document, indent=2)

    terminals_json = {
        "$schema": "corpus.schema.json",
        "documentId": doc_id + ".doc",
        "id": doc_id + ".terminals",
        "type": "terminal",
        "content": {
            "dataLayerRef": doc_id + ".data",
            "terminals": segments["terminals"]
        }
    }
    json.dump(terminals_json, f_terminals, indent=2)

    datalayer_json = {
        "$schema": "corpus.schema.json",
        "id": doc_id + ".data",
        "type": "data",
        "documentId": doc_id + ".doc",
        "content": {
            "text": " ".join(segments["data"])
        }
    }
    json.dump(datalayer_json, f_datalayer, indent=2)

    tokens_json = {
        "$schema": "corpus.schema.json",
        "id": doc_id + ".tokens",
        "documentId": doc_id + ".document",
        "type": "annotation",
        "metadata": {
            "annotationType": "tokenization",
            "annotationSource": "",
            "created": ""
        },
        "content":{
            "layerRefs": [doc_id + ".terminals"],
            "annotationNodes": segments["tokens"]
        }
    }
    json.dump(tokens_json, f_tokens, indent=2)

    sentences_json = {
        "$schema": "corpus.schema.json",
        "id": doc_id + ".sentences",
        "documentId": doc_id + ".document",
        "type": "annotation",
        "metadata": {
            "annotationTypes": ["segmentation"],
            "annotationSource": "",
            "created": ""
        },
        "content": {
            "layerRefs": [doc_id + ".tokens"],
            "annotationNodes": segments["sentences"]
        }
    }
    json.dump(sentences_json, f_sentences, indent=2)


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
        for doc_id, doc, segments in my_document_reader:
            # open output files
            output_file = join(args.out_dir, f +"."+doc_id)
            f_datalayer = io.open(output_file + ".datalayer.json", mode="w", encoding="utf-8")
            f_document = io.open(output_file + ".document.json", mode="w", encoding="utf-8")
            f_sentences = io.open(output_file + ".sentences.json", mode="w", encoding="utf-8")
            f_terminals = io.open(output_file + ".terminals.json", mode="w", encoding="utf-8")
            f_tokens = io.open(output_file + ".tokens.json", mode="w", encoding="utf-8")

            write_document(doc_id, doc, segments, f_datalayer, f_document, f_sentences, f_terminals, f_tokens)

            # close all files
            f_datalayer.close()
            f_document.close()
            f_sentences.close()
            f_terminals.close()
            f_tokens.close()
            print("Wrote files with prefix", output_file)
        f_input.close()
