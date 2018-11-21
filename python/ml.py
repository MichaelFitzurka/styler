import java_lang_utils as jlu
import tensorflow as tf
import numpy as np
from tensorflow import keras
from javalang import tokenizer
from tqdm import tqdm
import os
import random
import json
import glob
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Activation, Flatten
from tensorflow.keras.layers import Conv2D, MaxPooling2D

# tf.logging.set_verbosity(tf.logging.INFO)

__synthetic_dir = '/home/benjaminl/Documents/synthetic-checkstyle-error-dataset/dataset'
__protocol = 'protocol1'

def get_dataset_dir(dataset):
    return f'{__synthetic_dir}/{__protocol}/{dataset}'

def get_sub_set_dir(dataset, sub_set):
    return f'{get_dataset_dir(dataset)}/{sub_set}'

def open_file(file):
    content = ''
    with open(file, 'r') as file:
        content = file.read()
    return content

def save_file(dir, file_name, content):
    with open(os.path.join(dir, file_name), 'w') as f:
        f.write(content)

def open_json(file):
    with open(file) as f:
        data = json.load(f)
        return data
    return None

def create_dir(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)

def list_folders(dir):
    return [ folder for folder in os.listdir(dir) if os.path.isdir(os.path.join(dir, folder)) ]

files = open_file('./ml_files.txt').split('\n')[:100]

def get_token_value(token):
    if isinstance(token, tokenizer.Keyword):
        return token.value
    if isinstance(token, tokenizer.Separator):
        return token.value

    if isinstance(token, tokenizer.Comment):
        return token.__class__.__name__
    if isinstance(token, tokenizer.Literal):
        return token.__class__.__name__
    if isinstance(token, tokenizer.Operator):
        return token.value
        if token.is_infix():
            return "InfixOperator"
        if token.is_prefix():
            return "PrefixOperator"
        if token.is_postfix():
            return "PostfixOperator"
        if token.is_assignment():
            return "AssignmentOperator"

    return token.__class__.__name__

def get_space_value(space):
    if space[0] == 0:
        return f'{space[1]}_SP'
    else:
        result = f'{space[0]}_NL'
        if space[1] == 0:
            pass
        elif space[1] > 0:
            result += f'_{space[1]}_ID'
        else:
            result += f'_{-space[1]}_DD'
        return result

def build_vocabulary(files):
    count = {}
    tokenized_files = [ jlu.tokenize_with_white_space(jlu.open_file(path)) for path in files ]
    whitespace_id = set()

    threshold = 30

    for spaces, tokens in tokenized_files:
        whitespace_id = set(spaces) | whitespace_id
        for token in tokens:
            name = get_token_value(token)
            if not name in count:
                count[name] = 0
            count[name] += 1

    litterals = list(filter(lambda key: count[key] >= threshold, count.keys()))
    litterals = { key:value for key, value in zip(litterals, range(len(litterals))) }

    whitespace_id = { key:value for key, value in zip(whitespace_id, range(len(whitespace_id))) }

    len_litterals = len(litterals)
    len_whitespace = len(whitespace_id)
    vec_size = len_litterals + 1 + len_whitespace

    def get_vector(space, token):
        vector = np.array([0]*vec_size)
        if get_token_value(token) in litterals:
            vector[litterals[get_token_value(token)]] = 1
        else:
            vector[len_litterals] = 1
        vector[len_litterals + 1 + whitespace_id[space]] = 1
        return vector

    print(litterals.keys())

    return get_vector, whitespace_id

def tokenize_errored_file(file, file_orig, error):
    spaces, tokens = jlu.tokenize_with_white_space(jlu.open_file(file))
    token_started = False
    from_token = -1
    to_token = -1
    count = 0
    tokens_errored = []
    for token, space in zip(tokens, spaces):
        if not token_started and int(error['line']) == token.position[0]:
            token_started = True
            tokens_errored.append(f'<{error["type"]}>')
            from_token = count
        if token_started and  int(error['line']) < token.position[0]:
            token_started = False
            tokens_errored.append(f'</{error["type"]}>')
            to_token = count
        tokens_errored.append(get_token_value(token))
        tokens_errored.append(get_space_value(space))
        count += 1
    spaces, tokens = jlu.tokenize_with_white_space(jlu.open_file(file_orig))
    tokens_correct = []
    for token, space in zip(tokens[from_token:to_token], spaces[from_token:to_token]):
        tokens_correct.append(get_token_value(token))
        tokens_correct.append(get_space_value(space))
    return tokens_errored, tokens_correct

def whatever(dataset, folder, id):
    dir = f'{get_dataset_dir(dataset)}/{folder}/{id}'
    file_name = [ java_file for java_file in glob.glob(f'{dir}/*.java') if 'orig' not in java_file ][0].split('/')[-1].split('.')[0]
    file = f'{dir}/{file_name}.java'
    file_orig = f'{dir}/{file_name}-orig.java'
    error_file = f'{dir}/metadata.json'
    error = open_json(error_file)
    return tokenize_errored_file(file, file_orig, error)

def gen_IO(dataset, target):
    create_dir(target)
    dir = get_dataset_dir(dataset)
    sub_sets = ['learning', 'validation', 'testing']
    for sub_set in sub_sets:
        sub_set_dir = get_sub_set_dir(dataset, sub_set)
        target_sub_set = f'{target}/{sub_set}'
        create_dir(target_sub_set)
        synthesis_error_ids = list_folders(sub_set_dir)
        for id in tqdm(synthesis_error_ids):
            tokens_errored, tokens_correct = whatever(dataset, sub_set, id)
            save_file(target_sub_set, f'{id}-I.txt', " ".join(tokens_errored))
            save_file(target_sub_set, f'{id}-O.txt', " ".join(tokens_correct))

def vectorize_file(path, vectorizer):
    spaces, tokens = jlu.tokenize_with_white_space(jlu.open_file(path))

    result = []
    for ws, t in zip(spaces, tokens):
        result.append(vectorizer(ws, t))

    return result

if __name__ == "__main__":
    gen_IO('spoon', './synthetic_data')
    # k = 20
    # vectorizer, whitespace_id = build_vocabulary(files)
    # print(len(whitespace_id))
    # data = []
    # for file in files:
    #     vector = []
    #     vector = vectorize_file(file, vectorizer)
    #     for i in range(k, len(vector) - k, 1):
    #         io = dict()
    #         io['input'] = np.array(vector[i-k:i+k+1]).copy()
    #         for i in range(len(whitespace_id)):
    #             io['input'][k][-1-i] = 0
    #         ws = vector[i][-len(whitespace_id):]
    #         i = 0
    #         j = 0
    #         for a in ws:
    #             if j == 0 and a == 1:
    #                 j = i
    #             i += 1
    #         # print(io['input'].shape)
    #         io['output'] = j
    #         # print(io['input'])
    #         data.append(io)
    # random.shuffle(data)
    # train_len = int(len(data) * 0.8)
    # train_data = data[:train_len]
    # test_data = data[train_len:]
    # print(f'Train files {train_len}')
    #
    # train_input = np.array([d['input'] for d in train_data])
    # train_labels = np.array([d['output'] for d in train_data])
    # #
    # test_input = np.array([d['input'] for d in test_data])
    # test_labels = np.array([d['output'] for d in test_data])
    #
    # print(train_input[0])
    # tf.app.run()
