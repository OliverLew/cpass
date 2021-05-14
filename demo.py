#!/usr/bin/env python3
import os
import urwid
from subprocess import run, PIPE


def debug(message):
    if os.getenv('DEBUG'):
        open('log', 'a').write(message + '\n')


class SelectableText(urwid.Text):
    def __init__(self, markup):
        super().__init__(markup, wrap='clip')

    def selectable(self):
        """ make the widget selectable for navigating """
        return True

    def keypress(self, size, key):
        """ let the widget pass through the keys """
        return key


class PassNode(urwid.AttrMap):
    def __init__(self, text):
        super().__init__(SelectableText(text), '',  'focus')
        self.node = self.original_widget.text


class SearchBox(urwid.Edit):
    def keypress(self, size, key):
        debug(key)
        if key in ['esc']:
            self.set_edit_text('')
            passui.contents['footer'] = (passui.footer, None)
            passui.set_focus('body')
            return None
        elif key in ['enter']:
            return None

        return super().keypress(size, key)


class PassList(urwid.ListBox):
    def __init__(self, body, root=None):
        self.root = root if root else ''
        super().__init__(body)

    def mouse_event(self, size, event, button, col, row, focus):
        debug("{} {} {} {} {} {} {}".format(
            size, event, button, col, row, focus, self.focus_position
        ))
        if button in [1] and row == self.focus_position:
            self.keypress(size, 'enter')
        elif button in [3]:
            self.keypress(size, 'left')
        elif button in [4]:
            self.keypress(size, 'up')
        elif button in [5]:
            self.keypress(size, 'down')
        else:
            return super().mouse_event(size, event, button, col, row, focus)

    def keypress(self, size, key):
        keymap = {
            'g': 'home',
            'G': 'end',
            'j': 'down',
            'k': 'up',
            'ctrl y': 'down',
            'ctrl e': 'up',
            'ctrl n': 'down',
            'ctrl p': 'up',
            'ctrl b': 'page up',
            'ctrl f': 'page down',
        }
        debug("{} {}".format(key, size))

        if key in keymap:
            return super().keypress(size, keymap[key])
        elif key in ['d']:
            if len(self.body) > 0:
                self.body.pop(self.focus_position)
        elif key in ['a']:
            self.body.insert(self.focus_position, PassNode('foonew'))
        elif key in ['/']:
            passui.contents['footer'] = (passui.edit, None)
            passui.set_focus('footer')
        elif key in ['ctrl d', 'ctrl u']:
            total = len(self.body)
            curr = self.focus_position
            offset = int(size[1] / 2)
            if key == 'ctrl u':
                self.set_focus(curr - offset if curr > offset - 1 else 0)
            if key == 'ctrl d':
                self.set_focus(curr + offset if curr < total - offset else total - 1)
        elif key in ['l', 'enter', 'right']:
            if self.focus.node in allnodes[self.root].dirs:
                self.root = os.path.join(self.root, self.focus.node)
                # this way the list itself is not replaced, same down there
                self.body[:] = [PassNode(node) for node in allnodes[self.root].contents()]
        elif key in ['h', 'left']:
            self.root = os.path.dirname(self.root)
            self.body[:] = [PassNode(node) for node in allnodes[self.root].contents()]
        else:
            return super().keypress(size, key)


class Directory():
    def __init__(self, root, dirs, files):
        self.root = root
        self.dirs = dirs
        self.files = files
        self.pos = 0

    def contents(self):
        return self.dirs + self.files


class UI(urwid.Frame):
    def __init__(self):
        self._last_preview = None
        self.app_string = 'Pass tui'
        header = urwid.AttrMap(urwid.Text(''), 'border')
        footer = urwid.AttrMap(urwid.Text('', align='right'), 'border')
        self.divider = urwid.AttrMap(urwid.Divider('-'), 'border')
        self.preview = urwid.Filler(urwid.Text(''), valign='top')
        self.edit = SearchBox("/")

        self.walker = urwid.SimpleListWalker([
            PassNode(directory) for directory in allnodes[''].contents()
        ])
        self.listbox = PassList(self.walker)
        if arg_preview in ['side', 'horizontal']:
            self.middle = urwid.Columns([self.listbox, self.preview], dividechars=1)
        elif arg_preview in ['bottom', 'vertical']:
            self.middle = urwid.Pile([self.listbox, ('pack', self.divider), self.preview])

        # update upon list operations
        urwid.connect_signal(self.walker, 'modified', self.update_view)
        super().__init__(self.middle, self.header_widget, self.footer_widget, focus_part='body')

    def update_view(self):
        if self.listbox.focus is None:
            self.footer.original_widget.set_text("0/0")
            return

        text = self.listbox.focus.node
        node = os.path.join(self.listbox.root, text)

        if node == self._last_preview:
            # don't update if the node does not change
            # still problematic due to I am using listbox.keypress() to navigate, what urwid
            # is doing under the ground might trigger this function multiple times when there
            # is no need. investigation is required, otherwise the navigation need to be
            # impletemented manually in a low level.
            # I intended not to have this code, since this does not solve all problems
            # at once
            return

        if text in allnodes[self.listbox.root].dirs:
            preview = "\n".join(allnodes[node].contents())
        else:
            preview = password_store.show(node)
            debug("password: " + preview)
            debug("list length: {}".format(len(self.listbox.body)))
        self.preview.original_widget.set_text(preview)
        self._last_preview = node

        self.contents['header'][0].original_widget.set_text('{}: {}'.format(
            self.app_string,
            os.path.join(password_store.PASS_DIR, self.listbox.root)
        ))
        self.contents['footer'][0].original_widget.set_text("{}/{}".format(
            self.listbox.focus_position + 1,
            len(self.listbox.body)
        ))


class Pass():
    """ pass operations """
    def __init__(self):
        HOME = os.getenv("HOME")
        FALLBACK_PASS_DIR = os.path.join(HOME, ".password_store")
        self.PASS_DIR = os.getenv("PASSWORD_STORE_DIR", FALLBACK_PASS_DIR)

    def extract_all(self):
        dir_contents = {}
        for root, dirs, files in os.walk(self.PASS_DIR, topdown=True):
            if not root.startswith(os.path.join(self.PASS_DIR, '.git')):
                dirs = [os.path.join('', d) for d in dirs if d != '.git']
                files = [file.rstrip('.gpg') for file in files if file.endswith('.gpg')]
                relroot = os.path.normpath(os.path.join('', os.path.relpath(root, self.PASS_DIR)))
                if relroot == '.':
                    relroot = ''
                dir_contents[relroot] = Directory(relroot, dirs, files)
        return dir_contents

    def show(self, node):
        result = run(['pass', 'show', node], stdout=PIPE, stderr=PIPE, text=True)
        return result.stderr if result.returncode else result.stdout

def unhandled_input(key):
    if key in ['q', 'Q']:
        raise urwid.ExitMainLoop()
    return True


if __name__ == '__main__':
    arg_preview = 'side'

    # pass backend
    password_store = Pass()
    allnodes = password_store.extract_all()

    # UI
    passui = UI()
    # manually update when first opening the program
    passui.update_view()

    # main loop
    loop = urwid.MainLoop(passui, unhandled_input=unhandled_input, palette=[
        # name          fg              bg              styles
        ('focus',       'black',        'dark cyan',    'standout'),
        ('border',      'light cyan',   'default'),
    ])
    # set the timeout after escape, or, set instant escape
    loop.screen.set_input_timeouts(complete_wait=0)
    loop.run()
