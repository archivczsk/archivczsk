'''
Created on 10.9.2012

@author: marko
'''

import traceback
from threading import Thread
from twisted.internet import defer
from twisted.python import failure
try:
	from Queue import Queue
except:
	from queue import Queue

from .logger import log
from ...compat import eCompatPythonMessagePump
from ..exceptions.addon import AddonThreadException
from .util import set_thread_name

# object for stopping workerThread
WorkerStop = object()

# queue for task to be executed in workerThread
task_queue = Queue(1)

# input queue to send results from reactor thread to running function in workerThread
fnc_in_queue = Queue(1)

#output queue to send function decorated by callFromThread from workerThread to reactor thread and run it there
fnc_out_queue = Queue(1)

def run_in_main_thread(val):
	#print 'run_in_main_thread -', currentThread().getName()
	fnc_out_queue.get()()

m_pump = None

def callFromThread(func):
	"""calls function from child thread in main(reactor) thread,
		and wait(in child thread) for result. Used mainly for GUI calls
		"""
	def wrapped(*args, **kwargs):

		def _callFromThread():
			result = defer.maybeDeferred(func, *args, **kwargs)
			result.addBoth(fnc_in_queue.put)

		fnc_out_queue.put(_callFromThread)
		m_pump.send(0)
		result = fnc_in_queue.get()
		log.debug("result is %s" % str(result))
		if isinstance(result, failure.Failure):
			result.raiseException()
		return result
	return wrapped


class WorkerThread(Thread):

	def __init__(self):
		Thread.__init__(self)
		self.name = "ArchivCZSK-workerThread"
		self.active_task = None

	def get_active_task(self):
		return self.active_task

	def run(self):
		set_thread_name(self.name)
		task = task_queue.get()
		while task is not WorkerStop:
			self.active_task = task

			try:
				result = task.fnc(*task.args, **task.kwargs)
				success = True
			except:
				success = False
				result = failure.Failure()

			self.active_task = None

			try:
				if not task._aborted:
					task.onComplete(success, result)
				else:
					log.debug("[Task] aborted, not calling onComplete")
			except:
				log.error(traceback.format_exc())

			del task
			task = task_queue.get()
		log.debug("worker thread stopped")

	def stop(self):
		log.debug("stopping working thread")
		task_queue.put(WorkerStop)


class Task(object):
	"""Class for running single python task
		at time in worker thread"""

	worker_thread = None

	@staticmethod
	def get_active_task():
		return Task.worker_thread.get_active_task() if Task.worker_thread else None

	@staticmethod
	def startWorkerThread():
		log.debug("[Task] starting workerThread")
		global m_pump
		if m_pump is None:
			m_pump = eCompatPythonMessagePump(run_in_main_thread)
		Task.worker_thread = WorkerThread()
		Task.worker_thread.start()

	@staticmethod
	def stopWorkerThread():
		log.debug("[Task] stopping workerThread")
		Task.worker_thread.stop()
		Task.worker_thread.join()
		Task.worker_thread = None

		# flush fnc_out_queue if it's not empty
		log.debug("[Task] flushing fnc_out_queue")
		while True:
			try:
				f = fnc_out_queue.get(False)
			except:
				break
			f()

		global m_pump
		if m_pump is not None:
			m_pump.stop()
		m_pump = None

	def __init__(self, callback, fnc, *args, **kwargs):
		log.debug('[Task] initializing')
		self.callback = callback
		self.fnc = fnc
		self.args = args
		self.kwargs = kwargs
		self._running = False
		self._aborted = False
		self._canceling = False

	def run(self):
		self._running = True
		self._aborted = False
		self._canceling = False
		task_queue.put(self)
		log.debug('[Task] running')

	def setResume(self):
		log.debug("[Task] resuming")
		self._canceling = False

	def setCancel(self):
		""" setting flag to abort executing compatible task
			 (ie. controlling this flag in task execution) """

		log.debug('[Task] cancelling...')
		self._canceling = True

	def isCancelling(self):
		return self._canceling

	def onComplete(self, success, result):
		def wrapped_finish():
			self.callback(success, result)

		if success:
			log.debug('[Task] completed with success')
		else:
			log.debug('[Task] completed with failure')

		# To make sure that, when we abort processing of task,
		# that its always the same type of failure
		if self._canceling:
			success = False
			result = failure.Failure(AddonThreadException())
		fnc_out_queue.put(wrapped_finish)
		m_pump.send(0)

	def abort(self):
		log.debug('[Task] aborting')
		self._canceling = True
		self._aborted = True
		self.callback(False, failure.Failure(AddonThreadException()))
