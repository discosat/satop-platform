import ctypes
import enum
import os
import select
import sys

"""
/* Command return values */
#define SLASH_EXIT	    ( 1)
#define SLASH_SUCCESS	( 0)
#define SLASH_EUSAGE	(-1)
#define SLASH_EINVAL	(-2)
#define SLASH_ENOSPC	(-3)
#define SLASH_EIO	    (-4)
#define SLASH_ENOMEM	(-5)
#define SLASH_ENOENT	(-6)
#define SLASH_EBREAK	(-7)
"""


class SLASH_RETURN(enum.Enum):
    SLASH_EXIT = 1
    SLASH_SUCCESS = 0
    SLASH_EUSAGE = -1
    SLASH_EINVAL = -2
    SLASH_ENOSPC = -3
    SLASH_EIO = -4
    SLASH_ENOMEM = -5
    SLASH_ENOENT = -6
    SLASH_EBREAK = -7


class slash_command_t(ctypes.Structure):
    pass


class slash_t(ctypes.Structure):
    pass


"typedef int (*slash_waitfunc_t)(void *slash, unsigned int ms);"
slash_waitfunc_t = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.POINTER(slash_t), ctypes.c_uint
)

"typedef int (*slash_func_t)(struct slash *slash);"
slash_func_t = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(slash_t))

"typedef void (*slash_completer_func_t)(struct slash *slash, char * token);"
slash_completer_func_t = ctypes.CFUNCTYPE(
    None, ctypes.POINTER(slash_t), ctypes.c_char_p
)


slash_command_t._fields_ = [
    ("name", ctypes.c_char_p),
    ("func", slash_func_t),
    ("args", ctypes.c_char_p),
    ("completer", slash_completer_func_t),
    ("next", ctypes.POINTER(slash_command_t)),
]


slash_t._fields_ = [
    # struct termios original
    ("fd_write", ctypes.c_int),
    ("fd_read", ctypes.c_int),
    ("waitfunc", slash_waitfunc_t),
    ("use_activate", ctypes.c_bool),
    # Line editing
    ("line_size", ctypes.c_size_t),
    ("prompt", ctypes.c_char_p),
    ("prompt_length", ctypes.c_size_t),
    ("prompt_print_length", ctypes.c_size_t),
    ("buffer", ctypes.c_char_p),
    ("cursor", ctypes.c_size_t),
    ("length", ctypes.c_size_t),
    ("escaped", ctypes.c_bool),
    ("last_char", ctypes.c_char),
    # History
    ("history_size", ctypes.c_size_t),
    ("history_depth", ctypes.c_int),
    ("history_avail", ctypes.c_size_t),
    ("history_rewind_length", ctypes.c_int),
    ("history", ctypes.c_char_p),
    ("history_head", ctypes.c_char_p),
    ("history_tail", ctypes.c_char_p),
    ("history_cursor", ctypes.c_char_p),
    # Command interface
    ("argv", ctypes.POINTER(ctypes.c_char_p)),
    ("argc", ctypes.c_int),
    # getopt state
    ("optarg", ctypes.c_char_p),
    ("optind", ctypes.c_int),
    ("opterr", ctypes.c_int),
    ("optopt", ctypes.c_int),
    ("sp", ctypes.c_int),
    # Command list
    ("cmd_list", ctypes.POINTER(slash_command_t)),
    # Completions
    ("in_completion", ctypes.c_bool),
]

"""
/* Slash context */
struct slash {

	/* Terminal handling */
#ifdef SLASH_HAVE_TERMIOS_H
	struct termios original;
#endif

"""

slashlib = ctypes.CDLL("./libcsh.so")
libc = ctypes.CDLL(None)


"""
struct slash *slash_create(size_t line_size, size_t history_size);
void slash_destroy(struct slash *slash);
int slash_execute(struct slash *slash, char *line);
"""

slashlib.slash_create.argtypes = [ctypes.c_size_t, ctypes.c_size_t]
slashlib.slash_create.restype = ctypes.POINTER(slash_t)

slashlib.slash_destroy.argtypes = [ctypes.POINTER(slash_t)]
slashlib.slash_destroy.restype = None

slashlib.slash_execute.argtypes = [ctypes.POINTER(slash_t), ctypes.c_char_p]
slashlib.slash_execute.restype = ctypes.c_int

slash = None


def run(cmd):
    global slash
    if not slash:
        slash = slashlib.slash_create(64, 1024)
    print(">", cmd)

    pipe_out, pipe_in = os.pipe()
    stdout_fileno = sys.stdout.fileno()  # doesn't work in jupyter, where stdout is 39

    # Copy stdout
    stdout = os.dup(stdout_fileno)
    # Replace stdout with our write pipe
    os.dup2(pipe_in, stdout_fileno)

    res = slashlib.slash_execute(slash, cmd.encode("utf-8"))
    res = SLASH_RETURN(res)

    libc.fflush(None)

    out = b""
    while True:
        r, _, _ = select.select([pipe_out], [], [], 0)
        if not r:
            break
        out += os.read(pipe_out, 1024)

    os.close(pipe_in)
    os.close(pipe_out)
    os.dup2(stdout, stdout_fileno)

    print(out)
    return out, res


def execute_script(lines: list[str]):
    global slash
    if not slash:
        slash = slashlib.slash_create(64, 1024)

    stdout = os.dup(1)
    pipe_out, pipe_in = os.pipe()
    os.dup2(pipe_in, 1)

    for cmd in lines:
        res = slashlib.slash_execute(slash, cmd.encode("utf-8"))
        res = SLASH_RETURN(res)

        match res:
            case SLASH_RETURN.SLASH_EXIT:
                break
            case SLASH_RETURN.SLASH_SUCCESS:
                continue
            case _:
                break

    libc.fflush(None)
    os.close(pipe_in)

    out = b""
    while True:
        r, _, _ = select.select([pipe_out], [], [], 0)
        if not r:
            break
        out += os.read(pipe_out, 1024)

    os.close(pipe_out)
    os.dup2(stdout, 1)

    print(out)

    return out, res
