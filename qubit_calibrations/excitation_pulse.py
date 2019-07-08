from ..data_structures import *
from .. import data_reduce
from . import channel_amplitudes
#from 
import traceback
from . import Rabi
import pandas as pd

def get_rect_cos_pulse_sequence(device, channel_amplitudes, tail_length, length, phase):
	if tail_length > 0:	channel_pulses = [(c, device.pg.rect_cos, a*np.exp(1j*phase), tail_length) for c, a in channel_amplitudes.items()]
	else:				channel_pulses = [(c, device.pg.rect,	  a*np.exp(1j*phase)			 ) for c, a in channel_amplitudes.items()]
			
	return [device.pg.pmulti(length+2*tail_length, *tuple(channel_pulses))]

class rect_cos_excitation_pulse(measurement_state):
	def __init__(self, *args, **kwargs):
		self.device = args[0]
		if len(args) == 2 and isinstance(args[1], measurement_state) and not len(kwargs): # copy constructor
			super().__init__(args[1])
		else: # otherwise initialize from dict and device
			metadata = {'rotation_angle': str(kwargs['rotation_angle']),
						'pulse_type': 'rect',
						'length': str(kwargs['length']),
						'tail_length': str(kwargs['tail_length'])}
						
			if 'calibration_type' in kwargs:
				metadata['calibration_type'] = kwargs['calibration_type']
						
			references = {'channel_amplitudes': int(kwargs['channel_amplitudes']),
						  'Rabi_rect': int(kwargs['Rabi_rect_measurement'])}
			
			# check if such measurement exists
			try:
				measurement = self.device.exdir_db.select_measurement(measurement_type='qubit_excitation_pulse', metadata=metadata, references_that=references)
				super().__init__(measurement)
			except:
				traceback.print_exc()
				super().__init__(measurement_type='qubit_excitation_pulse', sample_name=self.device.exdir_db.sample_name, metadata=metadata, references=references)
				self.device.exdir_db.save_measurement(self)
				
		#inverse_references = {v:k for k,v in self.references.items()}
		#print ('inverse_references in __init__:', inverse_references)
		self.channel_amplitudes = channel_amplitudes.channel_amplitudes(self.device.exdir_db.select_measurement_by_id(self.references['channel_amplitudes']))
		
	def get_pulse_sequence(self, phase):
		return get_rect_cos_pulse_sequence(device = self.device, 
										   channel_amplitudes = self.channel_amplitudes, 
										   tail_length = float(self.metadata['tail_length']), 
										   length = float(self.metadata['length']),
										   phase = phase)
		
def get_excitation_pulse_from_Rabi_rect_fit(device, rotation_angle, Rabi_fit):
	#inverse_references = {v:k for k,v in Rabi_fit.references.items()}
	
	Rabi_rect_measurement = device.exdir_db.select_measurement_by_id( Rabi_fit.references['fit_source'])
	metadata = {'qubit_id': Rabi_rect_measurement.metadata['qubit_id'], 'rotation_angle': rotation_angle, 'calibration_type':'Rabi_rect'}
	channel_amplitudes = device.exdir_db.select_measurement(measurement_type='channel_amplitudes', references_this={'channel_amplitudes':Rabi_rect_measurement.id})
	assert(int(Rabi_fit.metadata['frequency_goodness_test']))
	
	f = float(Rabi_fit.metadata['f'])
	phi = float(Rabi_fit.metadata['phi'])
	tail_length = float(Rabi_rect_measurement.metadata['tail_length'])
	
	length = rotation_angle/(2*np.pi*f)
	return rect_cos_excitation_pulse(device, 
									 rotation_angle=rotation_angle, 
									 length=length, tail_length=tail_length, 
									 channel_amplitudes=channel_amplitudes.id, 
									 Rabi_rect_measurement=Rabi_rect_measurement.id)
	
def get_excitation_pulse(device, qubit_id, rotation_angle, channel_amplitudes_override=None):
	'''
	Rabi_goodness = []
	ex_channels_found = []

	for Rabi_measurement in device.exdir_db.select_measurements_db(measurement_type='Rabi_rect', metadata={'qubit_id':qubit_id}):
		try:
			Rabi_fit = None
			ex_channel = []
			metadata = {m.name:m.value for m in Rabi_measurement.metadata}
			# skip Rabi measurements that are n-d sweeps, we only try to use 1-d measurements here
			if 'extra_sweep_args' in metadata:
				if int(metadata['extra_sweep_args']):
					continue
			for reference in Rabi_measurement.reference_two:
				if reference.ref_type == 'fit_source':
					Rabi_fit = reference.this
			# check if there is a fit that can be used to evaluate the performance
			if not Rabi_fit:
				continue
			Rabi_fit = device.exdir_db.select_measurement_by_id(Rabi_fit.id)
			assert(int(Rabi_fit.metadata['frequency_goodness_test']))
			goodness_record = {'fit_id': Rabi_fit.id,
							   'score': min([float(Rabi_fit.metadata['num_periods_scan']), 
											 float(Rabi_fit.metadata['num_periods_decay'])])}
			# check if we have Rabi oscillations on all channels or not
			for reference in Rabi_measurement.reference_one:
				if reference.ref_type == 'channel_amplitudes':
					if channel_amplitudes_override:
						print ('channel_amplitudes_override: ', channel_amplitudes_override.id, channel_amplitudes_override.metadata)
						print ('reference: ', reference.that.id, reference.that.metadata)
						assert channel_amplitudes_override.id == reference.that.id	## if we are looking for a specific channel_amplitudes, skip all the others
							#raise 
					ex_channel = set([i.name for i in reference.that.metadata])
					
			Rabi_goodness.append(goodness_record)
			ex_channels_found.append(ex_channel)
		except:
			print ('Failed loading fit results of Rabi measurement {}'.format(Rabi_measurement.id))
			traceback.print_exc()
			pass
	'''
#	print ('ex_channels_found: ', ex_channels_found)
	for attempt_id in range(2):
		#fit = Rabi_measurements(device, 
		#	qubit_id=qubit_id, frequency=device.get_qubit_fq(qubit_id), frequency_tolerance = device.get_qubit_constant(qubit_id=qubit_id, name='frequency_rounding'))
		fits = device.exdir_db.db.db.select(Rabi_measurements_query(qubit_id=qubit_id, 
			frequency=device.get_qubit_fq(qubit_id), 
			frequency_tolerance = device.get_qubit_constant(qubit_id=qubit_id, name='frequency_rounding'),
			channel_amplitudes_override=channel_amplitudes_override.id if hasattr (channel_amplitudes_override, 'id') else channel_amplitudes_override))
		print ('good Rabi fits:', fits)
		for Rabi_fit_id in fits:
			try:
				print ('trying ', Rabi_fit_id)
				Rabi_fit = device.exdir_db.select_measurement_by_id(Rabi_fit_id)
				return get_excitation_pulse_from_Rabi_rect_fit(device, rotation_angle, Rabi_fit)
			except:
				print ('failed')
				traceback.print_exc()
				print ('Making excitation pulse from Rabi fit {} failed'.format(Rabi_fit_id))
				pass
		
		if attempt_id:	# if we have already tried to recalibrate and failed, die
			raise ValueError('Making excitation pulses from Rabi failed =(')
		
		if channel_amplitudes_override is None:
			Rabi.calibrate_all_single_channel_Rabi(device, _qubit_id=qubit_id)
		else:
			Rabi.Rabi_rect_adaptive(device, qubit_id=qubit_id, channel_amplitudes=channel_amplitudes_override)
'''
		
	if not channel_amplitudes_override: ## if this function is called to find Rabi oscillations excited from a specific channel (or channel combination), skip checking everythin
		for channel in device.get_qubit_excitation_channel_list(qubit_id):
			if set([channel]) not in ex_channels_found:
				print ('Rabi oscillations through channel '+channel+' not found in database, measuring default Rabi_rect')
				Rabi_fit = Rabi.Rabi_rect_adaptive(device, qubit_id, channel_amplitudes.channel_amplitudes(device, **{channel:1.0})).fit
				Rabi_goodness.append({'fit_id': Rabi_fit.id,
									  'score': min([float(Rabi_fit.metadata['num_periods_scan']), 
											float(Rabi_fit.metadata['num_periods_decay'])])*\
											float(Rabi_fit.metadata['frequency_goodness_test'])})
	else:
		if not len(ex_channels_found):
			Rabi_fit = Rabi.Rabi_rect_adaptive(device, qubit_id, channel_amplitudes_override).fit
			Rabi_goodness.append({'fit_id': Rabi_fit.id,
									  'score': min([float(Rabi_fit.metadata['num_periods_scan']), 
											float(Rabi_fit.metadata['num_periods_decay'])])*\
											float(Rabi_fit.metadata['frequency_goodness_test'])})
	
	for Rabi_fit_id in pd.DataFrame(Rabi_goodness).sort_values(by='score', ascending=False)['fit_id']:
		try:
			Rabi_fit = device.exdir_db.select_measurement_by_id(Rabi_fit_id)
			return get_excitation_pulse_from_Rabi_rect_fit(device, rotation_angle, Rabi_fit)
		except:
			traceback.print_exc()
			print ('Making excitation pulse from Rabi fit {} failed'.format(Rabi_fit_id))
			pass
			
	raise ValueError('Making excitation pulses from Rabi failed =(')
'''
	
def Rabi_measurements_query (qubit_id, frequency, frequency_tolerance, channel_amplitudes_override=None):
	'''
	Perfectly ugly query for retrieving Rabi oscillation measurements corresponding to a qubit, and, possibly, a 'channel'
	'''
	if channel_amplitudes_override is not None:
		channel_amplitudes_clause = 'AND channel_amplitudes.id = {}'.format(channel_amplitudes_override)
	else:
		channel_amplitudes_clause = ''
		
	query = '''SELECT fit_id FROM (
	SELECT 
		channel_amplitudes.id channel_amplitudes_id,
		fit.id fit_id, 
		LEAST(CAST(num_periods_scan.value AS DECIMAL), CAST(num_periods_decay.value AS DECIMAL)) score,
	--fit.id,
	--Rabi_freq.value as f,
	--num_periods_decay.value,
	--num_periods_scan.value,
	MIN(CAST (channel_calibration_frequency.value AS DECIMAL)) min_freq,
	MAX(CAST (channel_calibration_frequency.value AS DECIMAL)) max_freq
	
	--MAX(fit.id) fit_id
	
	--channel_amplitudes.*
	
	FROM
	data measurement
	
	INNER JOIN reference fit_measurement_reference ON
		fit_measurement_reference.ref_type = 'fit_source' AND
		fit_measurement_reference.that = measurement.id
	INNER JOIN data fit ON
		fit_measurement_reference.this = fit.id
		
	INNER JOIN metadata qubit_id_metadata ON
		qubit_id_metadata.data_id = measurement.id AND
		qubit_id_metadata.name = 'qubit_id' AND
		qubit_id_metadata.value = '{qubit_id}'
	
	INNER JOIN metadata frequency_goodness_test_metadata ON
		frequency_goodness_test_metadata.data_id = fit.id AND
		frequency_goodness_test_metadata.name = 'frequency_goodness_test' AND
		frequency_goodness_test_metadata.value = '1'
	
	INNER JOIN metadata MSE_rel_metadata ON
		MSE_rel_metadata.data_id = fit.id AND
		MSE_rel_metadata.name = 'MSE_rel'
	
	INNER JOIN reference channel_amplitudes_reference ON
		channel_amplitudes_reference.this = measurement.id AND
		channel_amplitudes_reference.ref_type = 'channel_amplitudes'
	
	INNER JOIN data channel_amplitudes ON
		channel_amplitudes.id = channel_amplitudes_reference.that
		
	INNER JOIN metadata channel ON
		channel.data_id = channel_amplitudes.id
		
	INNER JOIN reference channel_calibration_reference ON
		channel_calibration_reference.ref_type='channel_calibration' AND
		channel_calibration_reference.this = channel.data_id
	
	INNER JOIN data channel_calibration ON
		channel_calibration.id = channel_calibration_reference.that
		
	INNER JOIN metadata channel_calibration_frequency ON
		channel_calibration_frequency.data_id = channel_calibration.id AND
		channel_calibration_frequency.name = 'frequency' --AND
		--ABS(CAST (channel_calibration_frequency.value AS DECIMAL) - {frequency}) < {frequency_tolerance}
		
	INNER JOIN metadata Rabi_freq ON
		Rabi_freq.data_id = fit.id AND
		Rabi_freq.name = 'f'
	
	INNER JOIN metadata num_periods_decay ON
		num_periods_decay.data_id = fit.id AND
		num_periods_decay.name = 'num_periods_decay'
	
	INNER JOIN metadata num_periods_scan ON
		num_periods_scan.data_id = fit.id AND
		num_periods_scan.name = 'num_periods_scan'

	WHERE 
		measurement.measurement_type = 'Rabi_rect' AND
		(NOT measurement.invalid OR (measurement.invalid IS NULL))
		{channel_amplitudes_clause}
--		  (SELECT COUNT(*) FROM metadata 
--			  WHERE metadata.data_id = channel_amplitudes.id) = 1
			
	GROUP BY channel_amplitudes_id, 
			 fit.id, 
			 LEAST(CAST(num_periods_scan.value AS DECIMAL), CAST(num_periods_decay.value AS DECIMAL))	
	
	HAVING 
		ABS(MIN(CAST (channel_calibration_frequency.value AS DECIMAL))- {frequency})<{frequency_tolerance}
		AND ABS(MAX(CAST (channel_calibration_frequency.value AS DECIMAL))- {frequency})<{frequency_tolerance}

	ORDER BY 
		LEAST(CAST(num_periods_scan.value AS DECIMAL), CAST(num_periods_decay.value AS DECIMAL)) DESC
	
	) Rabi_measurements
'''
	return query.format(qubit_id=qubit_id, 
		frequency=frequency, 
		frequency_tolerance = frequency_tolerance,
		channel_amplitudes_clause = channel_amplitudes_clause)