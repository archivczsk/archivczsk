# -*- coding: utf-8 -*-

import traceback
from threading import Thread
from twisted.internet import defer
from twisted.python import failure
from Plugins.Extensions.archivCZSK.compat import eConnectCallback
from enigma import eTimer, ePythonMessagePump
from Plugins.Extensions.archivCZSK import log
from Plugins.Extensions.archivCZSK.engine.exceptions.addon import AddonServiceException

try:
	from Queue import Queue
except:
	from queue import Queue

# object for stopping workerThread
WorkerStop = object()

# queue for function to be executed in workerThread
fnc_queue = Queue(1)

# input queue to send results from reactor thread to running function in workerThread
fnc_in_queue = Queue(1)

#output queue to send function decorated by callFromThread from workerThread to reactor thread and run it there
fnc_out_queue = Queue(1)


def run_in_main_thread(val):
	#print 'run_in_main_thread -', currentThread().getName()
	fnc_out_queue.get()()


m_pump = None
m_pump_conn = None


def callFromService(func):
	"""calls function from child thread in main(reactor) thread,
		and wait(in child thread) for result. Used mainly for GUI calls
		"""

	def wrapped(*args, **kwargs):

		def _callFromService():
			result = defer.maybeDeferred(func, *args, **kwargs)
			result.addBoth(fnc_in_queue.put)

		fnc_out_queue.put(_callFromService)
		m_pump.send(0)
		result = fnc_in_queue.get()

		if isinstance(result, failure.Failure):
			result.raiseException()
		return result

	return wrapped


class BGServiceThread(Thread):

	def __init__(self):
		Thread.__init__(self)
		self.name = "ArchivCZSK-serviceThread"

	def run(self):
		o = fnc_queue.get()
		while o is not WorkerStop:
			function, args, kwargs, onResult = o
			del o
			try:
				result = function(*args, **kwargs)
				success = True
			except:
				log.error(traceback.format_exc())
				success = False
				result = failure.Failure()
			del function, args, kwargs
			try:
				onResult(success, result)
			except:
				log.error(traceback.format_exc())
			del onResult, result
			o = fnc_queue.get()
		log.debug("BGService worker thread stopped")

	def stop(self):
		log.debug("Stopping BGService working thread")
		fnc_queue.put(WorkerStop)


class BGServiceTask(object):
	"""Class for running single python task
		at time in service thread"""

	instance = None
	worker_thread = None

	@staticmethod
	def getInstance():
		return BGServiceTask.instance

	@staticmethod
	def startServiceThread():
		log.debug("[BGServiceTask] starting workerThread")
		global m_pump_conn
		if m_pump_conn is not None:
			del m_pump_conn
		global m_pump
		if m_pump is None:
			m_pump = ePythonMessagePump()
		m_pump_conn = eConnectCallback(m_pump.recv_msg, run_in_main_thread)
		BGServiceTask.worker_thread = BGServiceThread()
		BGServiceTask.worker_thread.start()

	@staticmethod
	def stopServiceThread():
		log.debug("[BGServiceTask] stopping workerThread")
		BGServiceTask.worker_thread.stop()
		BGServiceTask.worker_thread.join()
		BGServiceTask.worker_thread = None
		global m_pump_conn
		if m_pump_conn is not None:
			del m_pump_conn
		m_pump_conn = None
		global m_pump
		if m_pump is not None:
			m_pump.stop()
		m_pump = None

	@staticmethod
	def setPollingInterval(self, interval):
		self.polling_interval = interval

	def __init__(self, callback, fnc, *args, **kwargs):
		log.debug('[BGServiceTask] initializing')
		BGServiceTask.instance = self
		self.callback = callback
		self.fnc = fnc
		self.args = args
		self.kwargs = kwargs
		self._running = False
		self._aborted = False

	def run(self):
		# init work thread if needed
		if BGServiceTask.worker_thread == None:
			BGServiceTask.startServiceThread()

		log.debug('[BGServiceTask] running: %s' % str(self.fnc))
		self._running = True
		self._aborted = False

		o = (self.fnc, self.args, self.kwargs, self.onComplete)
		fnc_queue.put(o)

	def setResume(self):
		log.debug("[BGServiceTask] resuming")
		self._aborted = False

	def setCancel(self):
		""" setting flag to abort executing compatible task
			 (ie. controlling this flag in task execution) """

		log.debug('[BGServiceTask] cancelling...')
		self._aborted = True

	def isCancelling(self):
		return self._aborted

	def onComplete(self, success, result):

		def wrapped_finish():
			BGServiceTask.instance = None
			if self.callback:
				self.callback(success, result)

		if success:
			log.debug('[BGServiceTask] completed with success: %s' % str(self.fnc))
		else:
			log.debug('[BGServiceTask] completed with failure: %s' % str(self.fnc))

		# To make sure that, when we abort processing of task,
		# that its always the same type of failure
		if self._aborted:
			success = False
			result = failure.Failure(AddonServiceException())
		fnc_out_queue.put(wrapped_finish)
		m_pump.send(0)


class AddonBackgroundService(object):
	loop_timers = []
	one_shot_timers = []

	def __init__(self):
		pass

	@classmethod
	def run_task(cls, finish_cbk, fn, *args, **kwargs):
		def __run_task():
			cls.__run_task_internal(finish_cbk, fn, *args, **kwargs)

		cls.__run_task_delayed(500, __run_task)

	@classmethod
	def run_in_loop(cls, seconds_to_loop, fn, *args, **kwargs):
		cls.__run_task_internal(None, fn, *args, **kwargs)

		t = {}
		def __run_in_loop():
			cls.__run_task_internal(None, fn, *args, **kwargs)

		t['timer'] = eTimer()
		t['timer_conn'] = eConnectCallback(t['timer'].timeout, __run_in_loop)
		t['timer'].start(seconds_to_loop * 1000)
		cls.loop_timers.append(t)

	@classmethod
	def run_delayed(cls, delay_seconds, finish_cbk, cbk, *args, **kwargs):
		t = {}

		def __cleanup(success, result):
			del t['timer']
			del t['timer_conn']
			cls.one_shot_timers.remove(t)
			if finish_cbk:
				try:
					finish_cbk(success, result)
				except:
					log.error(traceback.format_exc())

		def __run_delayed():
			cls.__run_task_internal(__cleanup, cbk, *args, **kwargs)

		t['timer'] = eTimer()
		t['timer_conn'] = eConnectCallback(t['timer'].timeout, __run_delayed)
		t['timer'].start(delay_seconds * 1000, True)
		cls.one_shot_timers.append(t)

	@classmethod
	def __run_task_delayed(cls, delay_ms, cbk, *args, **kwargs):
		t = {}

		def __run_delayed():
			cbk(*args, **kwargs)
			del t['timer']
			del t['timer_conn']
			cls.one_shot_timers.remove(t)

		t['timer'] = eTimer()
		t['timer_conn'] = eConnectCallback(t['timer'].timeout, __run_delayed)
		t['timer'].start(delay_ms, True)
		cls.one_shot_timers.append(t)

	@classmethod
	def __run_task_internal(cls, finish_cbk, fn, *args, **kwargs):
		BGServiceTask(finish_cbk, fn, *args, **kwargs).run()
