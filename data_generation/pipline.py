import sys
import os
import argparse
from argparse import Namespace
import time
import json
import google.generativeai as genai
import typing_extensions as typing
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from openai import OpenAI

from math_expression_extractor import extract_formula
from query_gen import generate_query
from answer_retriever import generate_label
from context_collector import context_collect
from question_refiner import refine
from filter import filter_jsonl

   

if __name__ == '__main__':
    start = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf_path', type=str, default="E:\dmt\\formula\\Direct Preference Optimization--Your Language Model is Secretly a Reward Mode.pdf", help='the input file path')
    parser.add_argument('--model_name', type=str, default="gemini-2.0-flash-exp", help='the gemini model you want to use.')
    parser.add_argument('--output_dir', type=str, default="E:\\dmt\\formula\\generated\\final_test", help='output dir')
    args = parser.parse_args()
    print("pdf: " + args.pdf_path)
    print("model: " + args.model_name)
    print("output_dir: " + args.output_dir)

    
    prepare = time.time()

    # formula_path = os.path.join(args.output_dir, "api_"+args.pdf_path.split('\\')[-1][:-4]+"_formula.jsonl")
    # print(formula_path)
    formulas, f = extract_formula(args.model_name, args.pdf_path, args.output_dir)
    formulas_time = time.time()

    # query_path = os.path.join(args.output_dir, "api_"+args.pdf_path.split('\\')[-1][:-4]+"_query.jsonl")
    query, f = generate_query(args.model_name, formulas, args.pdf_path, args.output_dir)
    query_time = time.time()

    # QA_path = os.path.join(args.output_dir, "api_"+args.pdf_path.split('\\')[-1][:-4]+"_QA.jsonl")
    label,f = generate_label(args.model_name, query, args.pdf_path, args.output_dir)
    label_time = time.time()

    context_path = context_collect(f, args.pdf_path, args.output_dir)
    context_time=time.time()

    question_path = refine(context_path, args.pdf_path, args.output_dir)
    refine_time=time.time()

    filter_jsonl(question_path, args.output_dir, "deepseek-chat")
    filter_time = time.time()

    print(f"Time to configure model and upload file: {prepare - start:.2f} seconds")
    print(f"Time to extract formulas: {formulas_time - prepare:.2f} seconds")
    print(f"Time to generate queries: {query_time - formulas_time:.2f} seconds")
    print(f"Time to generate labels: {label_time - query_time:.2f} seconds")
    print(f"Time to collect context: {context_time - label_time:.2f} seconds")
    print(f"Time to refine query: {refine_time - context_time:.2f} seconds")
    print(f"Time to filter data: {filter_time - refine_time:.2f} seconds")
    print(f"Total time elapsed: {filter_time - start:.2f} seconds")