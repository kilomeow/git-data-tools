import os

import message
import diff
import gumtree_processing

import git

print_dict = lambda d: print('\n'.join(map(lambda p: '\n{0}:\n\t{1}'.format(*p), d.items())))

def process_git_repo(repo_path, skip, depth, gumtreebin, tmpdir, logfilepath):
    r = git.Repo(os.path.expanduser(repo_path))
    commits = r.iter_commits('master', max_count=depth)
    for i in range(skip+1): ac = next(commits)
    log = open(os.path.expanduser(logfilepath), 'w')
    commit_counter = 0
    matched_commits = 0
    for bc in commits:
        commit_message = ac.message
        cln_msg = message.clean_message(commit_message)
        diffs = ac.diff(bc)
        print('\n<== Processing commit with message:\n', commit_message)
        commit_counter += 1
        anymatch = False
        for d in diffs:
            if skip_diff(d): continue
            a, b, df = run_gumtree(d, gumtreebin, tmpdir)
            astdiff = diff.ASTDiff()
            astdiff.load_all_files(a, b, df)
            #m = message.find_code_mentions_in_commit_message(cln_msg, astdiff)
            #print(m)
            #if message.check_result(m):
            #    anymatch = True
            #    m['msg'] = cln_msg
            #    log.write(str(m)+',\n')
            #    log.flush()
            print_dict(astdiff.dump_changes())
        print('==>\n')
        matched_commits += anymatch
        print('[{0}/{1}]'.format(matched_commits, commit_counter))
        # print('1st message')
        # print(ac.message)
        # print('2st message')
        # print(bc.message)
        # print('----')
        ac = bc

suff = lambda s: s+'.java'

def run_gumtree(d, gumtreebin, tmpdir):
    names = ['a', 'b']
    for n in names:
        f = open(os.path.join(os.path.expanduser(tmpdir), suff(n)), 'wb')
        f.write(getattr(d, n+'_blob').data_stream.read())
    return gumtree_processing.process_diff(gumtreebin, tmpdir, map(suff, names), tmpdir)

def extract_ast_from_diff(d):
    a = diff.ASTree()
    b = diff.ASTree()
    a.parse_txt(d.a_blob.data_stream.read())
    b.parse_txt(d.b_blob.data_stream.read())

def skip_diff(d):
    if d.change_type != 'M':
        return True
    elif not d.a_path.endswith(suff('')):
        return True
    else:
        return False

if __name__ == '__main__':
    process_git_repo('~/intellij-community', 0, 1000, 
                     "~/gumtree-2.1.3-SNAPSHOT/bin/gumtree",
                     "~/tmp/",
                     "~/matches.json")
