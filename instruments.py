__all__ = []
import pkgutil
import inspect
import qsweepy.instrument_drivers

for loader, name, is_pkg in pkgutil.walk_packages(qsweepy.instrument_drivers.__path__):
	try:
		module = loader.find_module(name).load_module(name)

		for name, value in inspect.getmembers(module):
			if name.startswith('__'):
				continue
	
			globals()[name] = value
			__all__.append(name)
	except Exception as e:
		print ('Failed loading module '+name+': ', e)
		