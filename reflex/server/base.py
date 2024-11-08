from abc import abstractmethod, ABCMeta

from reflex.base import Base


class CustomBackendServer(Base):
    
    @abstractmethod
    def run_prod(self):
        raise NotImplementedError()

    @abstractmethod
    def run_dev(self):
        raise NotImplementedError()
