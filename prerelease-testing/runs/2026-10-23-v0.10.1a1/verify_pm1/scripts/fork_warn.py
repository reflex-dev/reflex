import multiprocessing as mp, threading, time, os
threading.Thread(target=lambda: time.sleep(5), daemon=True).start()
p = mp.get_context("fork").Process(target=lambda: None); p.start(); p.join()
print("child exit", p.exitcode)
