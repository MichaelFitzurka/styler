# -*- coding: utf-8 -*-

import java_lang_utils as jlu
import checkstyle
import subprocess
import os
from Corpus import *
import shutil
import random
import configparser
import sys
import glob
from tqdm import tqdm
import uuid
from functools import reduce
import java_lang_utils


config = configparser.ConfigParser()
config.read('config.ini')

class Synthetic_Checkstyle_Error:

    def __init__(self, dir):
        self.dir = dir
        self.id = int(dir.split('/')[-1])
        self.metadata = None
        self.original = None
        self.errored = None
        self.file_name = glob.glob(f'{self.dir}/*.java')[0].split('/')[-1].split('.')[0]
        if 'orig' in self.file_name:
             self.file_name[:-5]

    def get_metadata(self):
        if not self.metadata:
            self.load_metadata()
        return self.metadata

    def get_original(self):
        if not self.original:
            self.load_original()
        return self.original

    def get_errored(self):
        if not self.errored:
            self.load_errored()
        return self.errored

    def get_errored_path(self):
        return f'{self.dir}/{self.file_name}.java'

    def get_original_path(self):
        return f'{self.dir}/{self.file_name}-orig.java'

    def get_metadata_path(self):
        return f'{self.dir}/metadata.json'

    def load_metadata(self):
        self.metadata = open_json(self.get_metadata_path())

    def load_original(self):
        self.original = open_file(self.get_original_path())

    def load_errored(self):
        self.errored = open_file(self.get_errored_path())

__experiments_dir = './experiments/ml'
__base_dir = config['DEFAULT']['SYNTHETIC_DIR']

# def gen_ugly(corpus):
#     modifications = {}
#     for id, file in corpus.get_files().items():
#         if id not in modifications:
#             modifications[id] = {}
#         modifications[id][folder] = {}
#         for index in range(n):
#             modifications[id][folder][index] = java_lang_utils.gen_ugly( file[2], self.get_dir( os.path.join("./ugly/" + str(id) + "/{}/".format(folder) + str(index) + "/")), action)

def get_experiment_dir(id):
    return f'{__experiments_dir}/{id}'

def get_dir(dir):
    return os.path.join(__base_dir, dir)

def get_repo_dir(repo):
    return get_dir(f'./dataset/protocol1/{repo}')

def get_repo_type_dir(repo, type):
    return get_dir(f'./dataset/protocol1/{repo}/{type}')

def get_synthetic_error_dir(repo, type, id):
    return get_dir(f'{get_repo_dir(repo)}/{type}/{id}')

def list_elements(repo, type):
    dir = get_repo_type_dir(repo, type)
    return [ element for element in os.listdir(dir) if os.path.isdir(get_synthetic_error_dir(repo, type, element)) ]

def list_folders(dir):
    return [ element for element in os.listdir(dir) if os.path.isdir(os.path.join(dir, element)) ]

def save_file(dir, file_name, content):
    with open(os.path.join(dir, file_name), 'w') as f:
        f.write(content)

def save_json(dir, file_name, content):
    with open(os.path.join(dir, file_name), 'w') as f:
        json.dump(content, f)

def open_file(file):
    content = ''
    with open(file, 'r') as file:
        content = file.read()
    return content

def open_json(file):
    with open(file) as f:
        data = json.load(f)
        return data
    return None

def create_dir(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)
    return dir

def copy_originals(corpus, repo_name):
    folder = os.path.join(get_repo_dir(repo_name), './originals')
    create_dir(folder)
    for id, file in corpus.files.items():
        create_dir(f'{folder}/{id}')
        shutil.copyfile(file[2], f'{folder}/{id}/{file[0]}')
        # print(corpus.files[file])

injection_operator_types={
'insertion-space': (1,0,0,0,0),
'insertion-tab': (0,1,0,0,0),
'insertion-newline': (0,0,1,0,0),
'deletion-space': (0,0,0,1,0),
'deletion-newline': (0,0,0,0,1)
}

def run_diff(fileA, fileB):
    cmd = f'diff {fileA} {fileB}'
    # print(cmd)
    process = subprocess.Popen(cmd.split(" "), stdout=subprocess.PIPE)
    output = process.communicate()[0]
    return output.decode("utf-8")

def gen_get_random_file(corpus, numbers):
    files = list(corpus.files.values())
    corpus_size = len(files)
    shuffle_list = random.sample(list(range(corpus_size)), corpus_size) # random.shuffled() shuffle the list and does not returned the shuffled list
    print(shuffle_list)
    total_numbers = sum(numbers.values())
    values = {}
    for goal in numbers.keys():
        to = round(numbers[goal]/total_numbers*corpus_size)
        values[goal] = shuffle_list[:to]
        shuffle_list = shuffle_list[to:]
    print(values)
    def get_file(goal):
        return files[random.choice(values[goal])]
    return get_file

def gen_errored(corpus, get_random_corpus_file, repo_name, goal, id):
    folder = os.path.join(get_repo_dir(repo_name), f'./{goal}/{id}')
    file =  get_random_corpus_file(goal)
    file_dir = file[2]
    file_name = file[0].split('.')[0]
    done = False
    error = None
    ugly_file = ""
    while not done:
        if os.path.exists(folder):
            shutil.rmtree(folder)
        create_dir(folder)
        injection_operator = random.choice(list(injection_operator_types.keys()))
        ugly_file = os.path.join(folder, f'./{file_name}.java')
        modification = jlu.gen_ugly(file_dir, folder, modification_number=injection_operator_types[injection_operator])
        # print(modification)
        if not jlu.check_well_formed(ugly_file):
            continue
        cs_result, number_of_errors = checkstyle.check(corpus.checkstyle, ugly_file)
        if number_of_errors != 1:
            continue
        error = list(cs_result.values())[0]['errors'][0]
        done = True

    original_file = os.path.join(folder, f'./{file_name}-orig.java')
    shutil.copyfile(file_dir, original_file)
    save_file(folder, 'diff.diff', run_diff(original_file, ugly_file))

    report = {}
    report['injection_operator'] = injection_operator
    report['line'] = error['line']
    if 'column' in error:
        report['column'] = error['column']
    report['message'] = error['message']
    report['type'] = error['source'].split('.')[-1][:-5]

    save_json(folder, 'metadata.json', report)


def gen_dataset(corpus, numbers):
    repo_name = corpus.name
    dir = get_repo_dir(repo_name)
    if os.path.exists(dir):
        shutil.rmtree(dir)
    create_dir(dir)
    save_json(dir, 'repo.json', corpus.info)
    get_random_corpus_file = gen_get_random_file(corpus, numbers)
    shutil.copyfile(corpus.checkstyle, os.path.join(dir, f'./checkstyle.xml'))
    for goal, number in numbers.items():
        for i in tqdm(range(number), desc=f'{repo_name}/{goal}'):
            gen_errored(corpus, get_random_corpus_file, repo_name, goal, i)
    # copy_originals(corpus, repo_name)

def map_and_count(reducer, data):
    result = {}
    for element in map(reducer, data):
        if element not in result:
            result[element] = 0
        result[element] += 1
    return result


def load_repo(repo):
    return [ Synthetic_Checkstyle_Error('spoon', synthetic_error) for synthetic_error in list_elements(repo) ]

def summary(repo):
    synthetic_errors = load_repo(repo)
    results = {}
    results['type_count'] = map_and_count(lambda x: x.get_metadata()['type'], synthetic_errors)
    results['operator_count'] = map_and_count(lambda x: x.get_metadata()['injection_operator'], synthetic_errors)
    results['file_count'] = map_and_count(lambda x: x.file_name, synthetic_errors)
    print(results)
    save_json(get_repo_dir(repo), 'stats.json', results)

###  Experiment ####

def copy_uglies(from_dir, to_dir):
    create_dir(to_dir)
    uglies = [
        java_file for java_file in glob.glob(f'{from_dir}/*/*.java')
        if 'orig' not in java_file
    ]
    for file in tqdm(uglies, desc='Copy uglies'):
        id, file_name = file.split('/')[-2:]
        target = os.path.join(to_dir, id)
        create_dir(target)
        target_file = os.path.join(target, file_name)
        shutil.copy(file, target_file)
        # metadata
        metadata_file = file[:file.rfind('/')] + '/metadata.json'
        target_metadata = os.path.join(target, 'metadata.json')
        shutil.copy(metadata_file, target_metadata)


def with_index(iterator):
    return zip(iterator, range(len(iterator)))

def copy_origs(from_dir, to_dir):
    create_dir(to_dir)
    origs = set([
        file.split('/')[-1]
        for file in glob.glob(f'{from_dir}/*/*-orig.java')
    ])
    for file_name, index in tqdm(with_index(origs), desc='Copy origs', total=len(origs)):
        file_dir = glob.glob(f'{from_dir}/*/{file_name}')[0]
        target = os.path.join(to_dir, str(index))
        create_dir(target)
        target_file = os.path.join(target, file_name)
        shutil.copy(file_dir, target_file)

def gen_experiment(dataset_name):
    dir = create_dir(get_repo_dir(dataset_name))
    experiment_id = dataset_name
    target = get_experiment_dir(experiment_id)
    create_dir(target)
    shutil.copy(os.path.join(dir, 'checkstyle.xml'), os.path.join(target, 'checkstyle.xml'))
    shutil.copy(os.path.join(dir, 'repo.json'), os.path.join(target, 'metadata.json'))
    ugly_dir = create_dir(os.path.join(target, 'ugly'))
    copy_uglies(os.path.join(dir, 'testing'), ugly_dir)
    orig_dir = create_dir(os.path.join(target, 'orig'))
    copy_origs(os.path.join(dir, 'learning'), orig_dir)

def gen_repaired(tool, dir, dataset_metadata):
    ugly_dir = os.path.join(dir, 'ugly')
    orig_dir = os.path.join(dir, 'orig')
    bin_dir = os.path.join(dir, 'bin')
    tool_dir = os.path.join(dir, tool)
    checkstyle_rules = os.path.join(dir, 'checkstyle.xml')
    call_repair_tool(tool, orig_dir, ugly_dir, tool_dir, dataset_metadata)
    parse_exception_files = move_parse_exception_files(tool_dir, bin_dir)
    return tool, dir

def get_checkstyle_results(tool, dir):
    tool_dir = os.path.join(dir, tool)
    ugly_dir = os.path.join(dir, 'ugly')
    orig_dir = os.path.join(dir, 'orig')
    file_name = f'checkstyle_results_{tool}.json'
    file_dir = f'{dir}/{file_name}'
    results_json = {}
    if os.path.exists(file_dir):
        results_json = open_json(file_dir)
    else:
        checkstyle_rules = os.path.join(dir, 'checkstyle.xml')
        checkstyle_results, number_of_errors = checkstyle.check(checkstyle_rules, tool_dir)
        results_json['checkstyle_results'] = checkstyle_results
        results_json['number_of_errors'] = number_of_errors
        save_json(dir, file_name, results_json)
    return results_json['checkstyle_results'], results_json['number_of_errors']

def get_repaired(tool, dir):
    checkstyle_results, number_of_errors = get_checkstyle_results(tool, dir)
    return [
        file.split('/')[-2]
        for file, result in checkstyle_results.items() if len(result['errors']) == 0
    ]

def run_experiment(dataset_name):
    experiment_id = dataset_name
    dir = get_experiment_dir(experiment_id)
    ugly_dir = os.path.join(dir, 'ugly')
    orig_dir = os.path.join(dir, 'orig')
    dataset_metadata = open_json(os.path.join(dir, 'metadata.json'))
    # checkstyle_results, number_of_errors = get_checkstyle_results(*gen_repaired('naturalize', dir, dataset_metadata))
    tools = ['naturalize', 'codebuff', 'naturalize_sniper', 'codebuff_sniper']
    for tool in tqdm(tools, desc='gen'):
        gen_repaired(tool, dir, dataset_metadata)

    repaired = {}
    for tool in tqdm(tools, desc=''):
        repaired[tool] = get_repaired(tool, dir)
    if 'naturalize_sniper' in tools and 'codebuff_sniper' in tools:
        repaired['loriot_repair'] = list(set(repaired['naturalize_sniper']) | set(repaired['codebuff_sniper']))
    # repaired_codebuff_sniper = get_repaired('codebuff_sniper', dir)
    # checkstyle_results, number_of_errors = checkstyle_results('naturalize_sniper', dir)
    pp.pprint({
        key:len(repaired_files)
        for key, repaired_files in repaired.items()
    })

def call_java(jar, args):
    cmd = "java -jar {} {}".format(jar, " ".join(args))
    # print(cmd)
    process = subprocess.Popen(cmd.split(" "), stdout=subprocess.PIPE)
    output = process.communicate()[0]
    return output

def list_dir_full_path(dir):
    return [ os.path.join(dir, element) for element in os.listdir(dir) ]

def call_repair_tool(tool, orig_dir, ugly_dir, output_dir, dataset_metadata):
    if tool == 'naturalize':
        return call_naturalize(orig_dir, ugly_dir, output_dir)
    if tool == 'naturalize_sniper':
        return call_naturalize_sniper(orig_dir, ugly_dir, output_dir)
    if tool == 'codebuff':
        return call_codebuff(orig_dir, ugly_dir, output_dir, grammar=dataset_metadata['grammar'], indent=dataset_metadata['indent'])
    if tool == 'codebuff_sniper':
        return call_codebuff_sniper(orig_dir, ugly_dir, output_dir[:-7],output_dir)

def get_uglies(ugly_dir):
    uglies_dir = [
        error
        for error in list_dir_full_path(ugly_dir) if os.path.isdir(error)
    ]
    uglies = [
        Synthetic_Checkstyle_Error(error)
        for error in uglies_dir
    ]
    return uglies

def call_naturalize(orig_dir, ugly_dir, output_dir):
    args = ["-t " + orig_dir, "-o " + output_dir, "-f " + ugly_dir]
    return call_java("../jars/naturalize.jar", args)

def call_naturalize_sniper(orig_dir, ugly_dir, output_dir):
    create_dir(output_dir)
    # TODO rebuild with sniper ...
    args = ["-mode snipper", "-t " + orig_dir, "-o " + output_dir, "-f " + ugly_dir]
    uglies = get_uglies(ugly_dir)
    for ugly in uglies:
        path = ugly.get_errored_path()
    #     erorrs_lines = [ int(e["line"]) for e in file["errors"]]
        erorrs_lines = [ int(ugly.get_metadata()["line"]) ]
        (from_char, to_char) = java_lang_utils.get_char_pos_from_lines(path, min(erorrs_lines) - 1, max(erorrs_lines) + 1)
        args.append(path + ":" + str(from_char) + ',' + str(to_char))
    return call_java("../jars/naturalize.jar", args)

def call_codebuff(orig_dir, ugly_dir, output_dir, grammar = "Java8", indent=2):
    args = ["-g org.antlr.codebuff." + grammar, "-rule compilationUnit", "-corpus " + orig_dir, "-files java", "-comment LINE_COMMENT", "-indent " + str(indent), "-o " + output_dir]
    args.append(ugly_dir)
    return call_java("../jars/codebuff-1.5.1.jar", args)

def call_codebuff_sniper(orig_dir, ugly_dir, codebuff_dir, output_dir):
    uglies = get_uglies(ugly_dir)
    for ugly in uglies:
        file_path = ugly.get_errored_path()
        codebuff_path = f'{codebuff_dir}/{ugly.id}/{ugly.file_name}.java'
        output_path = f'{output_dir}/{ugly.id}/{ugly.file_name}.java'
        erorrs_lines = [ int(ugly.get_metadata()["line"]) ]
        from_line, to_line = (min(erorrs_lines) - 1, max(erorrs_lines) + 1)
        try:
            java_lang_utils.mix_files(file_path, codebuff_path, output_path, from_line, to_line=to_line )
        except FileNotFoundError:
            print("No file (probably codebuff trash)")

def move_parse_exception_files(from_dir, to_dir):
    files = java_lang_utils.get_bad_formated(from_dir)
    create_dir(to_dir)
    for file in files:
        shutil.move(file, f'{to_dir}/{uuid.uuid4().hex}.java')
    return files

if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'run':
        corpora = []
        for corpus in sys.argv[2:]:
            corpora.append( Corpus(config['CORPUS'][corpus], corpus) )
        share = { key:config['DATASHARE'].getint(key) for key in ['learning', 'validation', 'testing'] }
        for corpus in corpora:
            gen_dataset(corpus, share)
    if len(sys.argv) >= 2 and sys.argv[1] == 'exp':
        print(sys.argv[2:])
        for dataset in sys.argv[2:]:
            target = get_experiment_dir(dataset)
            if not os.path.exists(target):
                gen_experiment(dataset)
            run_experiment(dataset)
    if len(sys.argv) >= 2 and sys.argv[1] == 'analyse':
        summary('spoon')
