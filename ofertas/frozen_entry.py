import multiprocessing

from ofertas.main import main


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
