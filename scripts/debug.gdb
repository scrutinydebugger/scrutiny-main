# Don't stop on common signals, let them pass to the program
handle SIGHUP nostop pass
handle SIGINT nostop pass
handle SIGPIPE nostop pass
handle SIGALRM nostop pass
handle SIGTERM nostop pass
handle SIGUSR1 nostop pass
handle SIGUSR2 nostop pass
handle SIGCHLD nostop pass

# Stop on SIGSEGV and print backtrace
handle SIGSEGV stop print

define hook-stop
  if $_siginfo._si_signo == 11
    echo \n=== SEGFAULT DETECTED ===\n
    echo --- Backtrace ---\n
    backtrace full
    echo --- Registers ---\n
    info registers
    echo =========================\n
    continue
  end
end

run
