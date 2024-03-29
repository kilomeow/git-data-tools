import os

import rename_analysis

indent = "    "

def parse_numeric(s):
    a = [str()]
    for c in s:
        if c.isnumeric():
            a[-1] += c
        else:
            if a[-1]: a.append(str())
    if not a[-1]: a.pop(-1)
    return tuple(map(int, a))


class ASTBlock:
    def __init__(self):
        self.stype = str()
        self.addr = (-1, -1)
        self.parent = None

    def parse(self, s):
        w = s.split(" ")
        # print(w) # shows that everything is ok
        self.stype = w[0].strip(":")
        self.addr = parse_numeric(w[-1])

    def set_parent(self, n):
        self.parent = n

    def __str__(self):
        return self.stype+" "+str(self.addr)

    def __repr__(self):
        return str(self)


class ASTNode(ASTBlock):
    def __init__(self):
        super().__init__()
        self.children = list()
        self.fields = list()
        self.name = ''

    def add_child(self, n):
        n.set_parent(self)
        self.children.append(n)

    def add_field(self, f):
        f.set_parent(self)
        self.fields.append(f)

    def __getitem__(self, i):
        return self.children[i]

    def __repr__(self):
        s = super().__repr__()
        if not self.name:
            try:
                self.name = name_of(self)
            except:
                pass
        return s + " `{0}` ({1} children, {2} fields)".format(self.name, 
                                                              len(self.children), 
                                                              len(self.fields))


class ASTField(ASTBlock):
    def __init__(self):
        super().__init__()
        self.text = str()

    def parse(self, s):
        super().parse(s)
        w = s.split(" ")
        self.text = " ".join(w[1:-1])

    def __str__(self):
        return self.stype+": "+self.text+" "+str(self.addr)

    def __repr__(self):
        return str(self)


def prepare_line(l):
    indent_level = 0
    pure_line = ''
    is_identation = True
    for i in range(len(l)):
        if is_identation:
            t = i%len(indent)
            if l[i] == indent[t]:
                if t+1 == len(indent): indent_level += 1
            else:
                pure_line += l[i]
                is_identation = False
        else:
            if l[i] == '\n': break
            pure_line += l[i]
    return (indent_level, pure_line)


def parse_line(parent, l):
    if l.split(" ")[0].endswith(":"):
        f = ASTField()
        f.parse(l)
        parent.add_field(f)
        return f
    else:
        n = ASTNode()
        n.parse(l)
        parent.add_child(n)
        return n


def address_in(child_a, parent_a):
    return (child_a[0] >= parent_a[0]) and (child_a[1] <= parent_a[1])


def name_of(node):
    return next(filter(lambda f: f.stype == 'SimpleName', node.fields)).text

def name_of_method(node):
    return name_of(node.parent_class)+'.'+name_of(node)

def in_which(addr_list, addr):
    try:
        return next(filter(lambda a: address_in(addr, a), addr_list))
    except StopIteration:
        return


class ASTree:
    def __init__(self):
        self.blocks = dict()
        self.root = None
        self.classes = dict()
        self.methods = dict()

    def __getitem__(self, addr):
        return self.blocks[addr]

    def _add_block(self, b):
        self.blocks[b.addr] = b
        if b.stype == 'TYPE_DECLARATION_KIND':
            #if b.text == 'class':
            self.classes[b.parent.addr] = b.parent
        if b.stype == 'MethodDeclaration':
            self.methods[b.addr] = b
            b.parent_class = self.classes[in_which(self.classes.keys(), b.addr)]
    
    def add_root(self, n):
        self.root = n
        self._add_subtree(self.root)

    def _add_subtree(self, v):
        self._add_block(v)
        for f in v.fields: self._add_block(f)
        for c in v.children: self._add_subtree(c)

    def parse_file(self, fn):
        with open(os.path.expanduser(fn)) as f:
            self.parse_lines(f.readlines())
    
    def parse_txt(self, txt):
        self.parse_lines(txt.split('\n'))

    def parse_lines(self, lines):
        self.root = ASTNode()
        hierarchy = [self.root]
        for l in lines:
            level, pl = prepare_line(l)
            b = parse_line(hierarchy[level], pl)
            self._add_block(b)
            if type(b) == ASTNode:
                if len(hierarchy) > level + 1:
                    hierarchy[level+1] = b
                else:
                    hierarchy.append(b)
        self.root = self.root[0]
    
    def in_which_class(self, node):
        return self.blocks[in_which(self.classes.keys(), node.addr)]

    def in_which_method(self, node):
        return self.blocks[in_which(self.methods.keys(), node.addr)]


class ASTDiff:
    def __init__(self, src=None, dest=None):
        self.a = src
        self.b = dest
        self.matches = list()
        self.actions = list()

    def load_json_file(self, fn):
        import json
        with open(os.path.expanduser(fn)) as f:
            d = json.loads(f.read())
            self.load_matches(d["matches"])
            self.load_actions(d["actions"])

    def load_all_files(self, a_fn, b_fn, diff_fn):
        self.a, self.b = ASTree(), ASTree()
        self.a.parse_file(a_fn)
        self.b.parse_file(b_fn)
        self.load_json_file(diff_fn)

    def load_matches(self, match_list):
        parse_addr = lambda s: parse_numeric(s.split(" ")[-1])
        for m in match_list:
            am_addr = parse_addr(m["src"])
            bm_addr = parse_addr(m["dest"])
            self.a[am_addr], self.b[bm_addr] # check
            self.matches.append((am_addr, bm_addr))

    def load_actions(self, action_list):
        update_node_pt = 0
        for a in action_list:
            da = DiffAction(a)
            # special presorting -- 'update-node' must be first
            if da.stype == 'update-node':
                self.actions.insert(update_node_pt, da)
                update_node_pt += 1
            else:
                self.actions.append(da)
        self.process_actions()
    
    def src2dest(self, src_a):
        return next(filter(lambda m: m[0] == src_a, self.matches))[1]
    
    def dest2src(self, dest_a):
        return next(filter(lambda m: m[1] == dest_a, self.matches))[0]
            
    def process_actions(self):
        # here also must be clasess
        self.removed_methods = dict()
        self.new_methods = dict()
        self.updated_methods = dict()
        self.moved_blocks = list()
        self.updated_classes = dict()
        self.renames = dict()

        rawbug = "{0}: gumtree bug, method {1} is already marked as updated"
        bug = lambda a, addr: rawbug.format(a.stype, name_of(self.updated_methods[addr]))

        self.size = 0

        for a in self.actions:
            if a.stype == 'update-node':
                # updated methods
                for ma, m in self.a.methods.items():
                    if ma in self.updated_methods.keys(): continue
                    if address_in(a.addr, ma): self.updated_methods[ma] = m
                    c = in_which(self.a.classes.keys(), a.addr)
                    if c: self.updated_classes[c] = self.a[c]
                # renames
                if a.raw["tree"].startswith("SimpleName"): # if rename
                    self.renames[a.addr] = rename_analysis.parse_rename(a.raw)
            elif a.stype == 'insert-node':
                # print('insert node!', self.b[a.addr])
                if a.addr in map(self.src2dest, self.updated_methods.keys()):
                    # print(bug(a, self.dest2src(a.addr)))
                    continue
                if a.addr not in self.b.methods.keys(): continue
                m = self.b.methods[a.addr]
                self.new_methods[m.addr] = m
                c = in_which(self.b.classes.keys(), a.addr)
                if c: self.updated_classes[c] = self.b[c]
            elif a.stype == 'delete-node':
                if a.addr in self.updated_methods.keys():
                    # print(bug(a, a.addr))
                    continue
                if a.addr not in self.a.methods.keys(): continue
                m = self.a.methods[a.addr]
                self.removed_methods[m.addr] = m
                c = in_which(self.a.classes.keys(), a.addr)
                if c: self.updated_classes[c] = self.a[c]
            elif a.stype == 'move-tree':
                self.moved_blocks.append(a.addr)
            self.size += 1
                
        # full names of methods
        namesd = lambda d: {name_of_method(m):a for a, m in d.items()}
        new_names = namesd(self.new_methods)
        rmv_names = namesd(self.removed_methods)
        upd_names = namesd(self.updated_methods)
        # delete methods from new or removed if they are already in updated_methods
        for um in upd_names.keys():
            if um in new_names.keys():
                self.new_methods.pop(new_names[um])
            if um in rmv_names.keys():
                self.removed_methods.pop(rmv_names[um])
        # now moving new and removed methods with same name to category of updated_methods
        matched_names = set(new_names.keys()).intersection(set(rmv_names.keys()))
        for mn in matched_names:
            addr_b = new_names[mn]
            addr_a = rmv_names[mn]
            self.new_methods.pop(addr_b)
            m = self.removed_methods.pop(addr_a)
            self.updated_methods[addr_a] = m
        
        self.method_extractions = list(map(self.b.methods.__getitem__, 
                                      filter(lambda a: a,
                                             map(lambda a: in_which(self.b.methods.keys(), a),
                                                 self.moved_blocks))))
    
    # def dump_changes(self):
    #     d = dict()
    #     return {k:getattr(self, k) for k in ['removed_methods',
    #                                          'new_methods',
    #                                          'updated_methods',
    #                                          'moved_blocks',
    #                                          'updated_classes',
    #                                          'renames',
    #                                          'size']}
    
    def actions_in_block(self, b):
        return filter(lambda a: address_in(a.addr, b.addr), self.actions)


class DiffAction:
    def __init__(self, data):
        self.raw = data
        self.stype = data['action']
        self.addr = parse_numeric(data['tree'].split(' ')[-1])
    
    def __repr__(self):
        return "{0} {1} \ndata:\n{2}".format(self.stype, self.addr, self.raw)
