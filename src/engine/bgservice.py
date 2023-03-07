# -*- coding: utf-8 -*-

import traceback
from threading import Thread
from twisted.internet import defer
from twisted.python import failure
from ..compat import eConnectCallback
from enigma import eTimer, ePythonMessagePump
from .. import log
from ..engine.exceptions.addon import AddonServiceException
from .tools.util import set_thread_name

try:
	from Queue import Queue
except:
	from queue import Queue


# object for stopping workerThread
WorkerStop = object()

# queue for function to be executed in workerThread
fnc_queue = Queue()

# input queue to send results from reactor thread to running function in workerThread
fnc_in_queue = Queue()

#output queue to send function decorated by callFromThread from workerThread to reactor thread and run it there
fnc_out_queue = Queue()


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
		self.stop_flag = False

	def run(self):
		set_thread_name(self.name)
		o = fnc_queue.get()
		while o is not WorkerStop:
			function, args, kwargs, onResult, service_name, task_name = o
			del o

			if not self.stop_flag:
				log.debug('[BGServiceThread] [%s] running task: %s' % (service_name, task_name))
				try:
					result = function(*args, **kwargs)
					success = True
				except:
					log.error(traceback.format_exc())
					success = False
					result = failure.Failure()
				log.debug('[BGServiceThread] [%s] task %s completed' % (service_name, task_name))
			else:
				log.debug('[BGServiceThread] [%s] not running task %s because of stop flag' % (service_name, task_name))
				success = False
				result = None

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
		self.stop_flag = True
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
	def startMessagePump():
		log.debug("[BGServiceTask] starting service -> reactor message pump")
		global m_pump_conn
		if m_pump_conn is not None:
			del m_pump_conn
		global m_pump
		if m_pump is None:
			m_pump = ePythonMessagePump()
		m_pump_conn = eConnectCallback(m_pump.recv_msg, run_in_main_thread)

	@staticmethod
	def startServiceThread():
		log.debug("[BGServiceTask] starting workerThread")
		BGServiceTask.worker_thread = BGServiceThread()
		BGServiceTask.worker_thread.start()

	@staticmethod
	def stopServiceThread():
		if BGServiceTask.worker_thread:
			log.debug("[BGServiceTask] stopping workerThread")
			BGServiceTask.worker_thread.stop()
			BGServiceTask.worker_thread.join()
			BGServiceTask.worker_thread = False

	@staticmethod
	def stopMessagePump():
		log.debug("[BGServiceTask] stopping service -> reactor message pump")
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

	def __init__(self, service_name, task_name, callback, fnc, *args, **kwargs):
		BGServiceTask.instance = self
		self.service_name = service_name
		self.task_name = task_name
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

		if BGServiceTask.worker_thread == False:
			log.debug('[BGServiceTask] [%s] not running task %s - worker thread was stopped' % (self.service_name, self.task_name))
			BGServiceTask.instance = None
			if self.callback:
				self.callback(False, None)
				return

		log.debug('[BGServiceTask] [%s] adding task to queue: %s' % (self.service_name, self.task_name))
		self._running = True
		self._aborted = False

		o = (self.fnc, self.args, self.kwargs, self.onComplete, self.service_name, self.task_name)
		fnc_queue.put(o)

	def setResume(self):
		log.debug('[BGServiceTask] [%s] resuming task %s...' % (self.service_name, self.task_name))
		self._aborted = False

	def setCancel(self):
		""" setting flag to abort executing compatible task
			 (ie. controlling this flag in task execution) """

		log.debug('[BGServiceTask] [%s] cancelling task %s...' % (self.service_name, self.task_name))
		self._aborted = True

	def isCancelling(self):
		return self._aborted

	def onComplete(self, success, result):

		def wrapped_finish():
			BGServiceTask.instance = None
			if self.callback:
				self.callback(success, result)

		if success:
			log.debug('[BGServiceTask] [%s] task %s completed with success' % (self.service_name, self.task_name))
		else:
			log.debug('[BGServiceTask] [%s] task %s completed with failure' % (self.service_name, self.task_name))

		# To make sure that, when we abort processing of task,
		# that its always the same type of failure
		if self._aborted:
			success = False
			result = failure.Failure(AddonServiceException())
		fnc_out_queue.put(wrapped_finish)
		m_pump.send(0)


# message pump must run all the time
BGServiceTask.startMessagePump()


class AddonBackgroundService(object):
	def __init__(self, name):
		self.loop_timers = []
		self.one_shot_timers = []
		self.name = name

	def run_task(self, name, finish_cbk, fn, *args, **kwargs):
		def __run_task():
			self.__run_task_internal(name, finish_cbk, fn, *args, **kwargs)

		self.__run_task_delayed(500, __run_task)

	def run_in_loop(self, name, seconds_to_loop, fn, *args, **kwargs):
		self.run_task(name, None, fn, *args, **kwargs)

		t = {}
		def __run_in_loop():
			self.__run_task_internal(name, None, fn, *args, **kwargs)

		def __init_timer():
			t['timer'] = eTimer()
			t['timer_conn'] = eConnectCallback(t['timer'].timeout, __run_in_loop)
			t['timer'].start(seconds_to_loop * 1000)
			self.loop_timers.append(t)

		# on DMM initialisation of eTimer must be done in main reactor thread
		fnc_out_queue.put(__init_timer)
		m_pump.send(0)
		return t

	def run_in_loop_stop(self, t):
		if t in self.loop_timers:
			self.loop_timers.remove(t)

			def __stop_timer():
				t['timer'].stop()
				del t['timer']
				del t['timer_conn']

			fnc_out_queue.put(__stop_timer)
			m_pump.send(0)

	def run_delayed(self, name, delay_seconds, finish_cbk, cbk, *args, **kwargs):
		t = {}

		def __cleanup(success, result):
			del t['timer']
			del t['timer_conn']
			self.one_shot_timers.remove(t)
			if finish_cbk:
				try:
					finish_cbk(success, result)
				except:
					log.error(traceback.format_exc())

		def __run_delayed():
			self.__run_task_internal(name, __cleanup, cbk, *args, **kwargs)

		def __init_timer():
			t['timer'] = eTimer()
			t['timer_conn'] = eConnectCallback(t['timer'].timeout, __run_delayed)
			t['timer'].start(delay_seconds * 1000, True)
			self.one_shot_timers.append(t)

		# on DMM initialisation of eTimer must be done in main reactor thread
		fnc_out_queue.put(__init_timer)
		m_pump.send(0)

	def __run_task_delayed(self, delay_ms, cbk, *args, **kwargs):
		t = {}

		def __run_delayed():
			cbk(*args, **kwargs)
			del t['timer']
			del t['timer_conn']
			self.one_shot_timers.remove(t)

		def __init_timer():
			t['timer'] = eTimer()
			t['timer_conn'] = eConnectCallback(t['timer'].timeout, __run_delayed)
			t['timer'].start(delay_ms, True)
			self.one_shot_timers.append(t)

		# on DMM initialisation of eTimer must be done in main reactor thread
		fnc_out_queue.put(__init_timer)
		m_pump.send(0)

	def __run_task_internal(self, name, finish_cbk, fn, *args, **kwargs):
		BGServiceTask(self.name, name, finish_cbk, fn, *args, **kwargs).run()
