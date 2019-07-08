from .readout_pulse import get_qubit_readout_pulse, get_uncalibrated_measurer
from ..fitters.exp_sin import exp_sin_fitter
from .channel_amplitudes import channel_amplitudes
import numpy as np
from . import excitation_pulse

def Ramsey(device, qubit_id, *extra_sweep_args, channel_amplitudes1=None, channel_amplitudes2=None, lengths=None, target_freq_offset=None, readout_delay=0):
	if type(lengths) is type(None):
		lengths = np.arange(0,  
							float(device.get_qubit_constant(qubit_id=qubit_id, name='Ramsey_length')),
							float(device.get_qubit_constant(qubit_id=qubit_id, name='Ramsey_step')))

	readout_pulse = get_qubit_readout_pulse(device, qubit_id)
	measurer = get_uncalibrated_measurer(device, qubit_id, readout_pulse)
	ex_pulse1 = excitation_pulse.get_excitation_pulse(device, qubit_id, np.pi/2., channel_amplitudes_override=channel_amplitudes1) 
	ex_pulse2 = excitation_pulse.get_excitation_pulse(device, qubit_id, np.pi/2., channel_amplitudes_override=channel_amplitudes2)
	
	def set_delay(length): 
		#ex_pulse_seq = [device.pg.pmulti(length+2*tail_length, *tuple(channel_pulses))]
		delay_seq = [device.pg.pmulti(length)]
		readout_delay_seq = [device.pg.pmulti(readout_delay)]
		readout_trigger_seq = device.trigger_readout_seq
		readout_pulse_seq = readout_pulse.pulse_sequence
		
		device.pg.set_seq(ex_pulse1.get_pulse_sequence(0)+\
						  delay_seq+\
						  ex_pulse2.get_pulse_sequence(length*target_freq_offset*2*np.pi)+\
						  readout_delay_seq+\
						  readout_trigger_seq+\
						  readout_pulse_seq)

	references = {'ex_pulse1':ex_pulse1.id, 
				  'ex_pulse2':ex_pulse2.id}
	references.update(measurer.references)
	fitter_arguments = ('iq'+qubit_id, exp_sin_fitter(), -1, np.arange(len(extra_sweep_args)))

	measurement = device.sweeper.sweep_fit_dataset_1d_onfly(measurer, 
											  *extra_sweep_args, 
											  (lengths, set_delay, 'Delay','s'), 
											  fitter_arguments = fitter_arguments,
											  measurement_type='Ramsey',
											  metadata={'qubit_id': qubit_id, 
														'extra_sweep_args':str(len(extra_sweep_args)), 
														'target_offset_freq': str(target_freq_offset),
														'readout_delay':str(readout_delay),
														},
											  references=references)
	
	return measurement

def get_Ramsey_pulse_frequency(device, Ramsey_measurement):	
	ex_pulse1 = select_measurement_by_id(Ramsey_measurement.references['ex_pulse1'])
	ex_pulse2 = select_measurement_by_id(Ramsey_measurement.references['ex_pulse1'])
	qubit_id = Ramsey_measurement.metadata['qubit_id']
	frequency_rounding = float(device.get_qubit_constant(qubit_id=qubit_id, name='frequency_rounding'))
	channel1_frequencies = []
	channel2_frequencies = []
	for reference in ex_pulse1.references:
		if 'channel_calibration_' in reference.name:
			channel1_frequencies.append([float(m.value) for m in reference.that.metadata if m.name == 'frequency'][0])
	for reference in ex_pulse2.references:
		if 'channel_calibration_' in reference.name:
			channel2_frequencies.append([float(m.value) for m in reference.that.metadata if m.name == 'frequency'][0])
	if np.max(channel1_frequencies) - np.min(channel1_frequencies) < frequency_rounding:
		raise Exception('Channel 1 frequency spreads are larger than frequency rounding')
	if np.max(channel2_frequencies) - np.min(channel2_frequencies) < frequency_rounding:
		raise Exception('Channel 2 frequency spreads are larger than frequency rounding')
	
def Ramsey_adaptive(device, qubit_id, set_frequency=True):
	# check if we have fitted Rabi measurements on this qubit-channel combo
	#Rabi_measurements = device.exdir_db.select_measurements_db(measurment_type='Rabi_rect', metadata={'qubit_id':qubit_id}, references={'channel_amplitudes': channel_amplitudes.id})
	#Rabi_fits = [exdir_db.references.this.filename for measurement in Rabi_measurements for references in measurement.reference_two if references.this.measurement_type=='fit_dataset_1d']
	
	#for fit in Rabi_fits:
	min_step = float(device.get_qubit_constant(qubit_id=qubit_id, name='adaptive_Rabi_min_step'))
	scan_points = int(device.get_qubit_constant(qubit_id=qubit_id, name='adaptive_Rabi_scan_points'))
	_range = float(device.get_qubit_constant(qubit_id=qubit_id, name='adaptive_Rabi_range'))
	max_scan_length = float(device.get_qubit_constant(qubit_id=qubit_id, name='adaptive_Ramsey_max_scan_length'))
	points_per_oscillation_target = float(device.get_qubit_constant(qubit_id=qubit_id, name='adaptive_Ramsey_points_per_oscillation'))
	frequency_rounding = float(device.get_qubit_constant(qubit_id=qubit_id, name='frequency_rounding'))
	target_offset = 1./(min_step*points_per_oscillation_target)
	
	lengths = np.arange(0, min_step*scan_points, min_step)
	while not np.max(lengths)>max_scan_length:
		#measurement = Rabi_rect(device, qubit_id, channel_amplitudes, lengths=delays)
		Ramsey_measurements = device.exdir_db.db.Data.select_by_sql(
		'''
		SELECT 
			Ramsey_fit.*
			FROM data Ramsey_fit 
			INNER JOIN Reference fit_measurement_reference ON 
				fit_measurement_reference.this = Ramsey_fit.id and fit_measurement_reference.ref_type='fit_source'
			INNER JOIN Data measurement ON 
				measurement.id = fit_measurement_reference.that
			INNER JOIN Metadata measurement_qubit_id ON
				(measurement_qubit_id.data_id = measurement.id 
					AND measurement_qubit_id.name='qubit_id'
					AND measurement_qubit_id.value='{qubit_id}')
			INNER JOIN Metadata fit_decay_goodness_test ON
				(fit_decay_goodness_test.data_id = Ramsey_fit.id 
					AND fit_decay_goodness_test.name='decay_goodness_test'
					AND fit_decay_goodness_test.value='1'
				)
			WHERE (NOT measurement.invalid OR measurement.invalid IS NULL)
				AND measurement.measurement_type='Ramsey'
		;
		'''.format(qubit_id=qubit_id))
		if len(Ramsey_measurements):
			break
		
		# go bown the rabbit hole for 
		measurement = Ramsey(device, qubit_id, lengths=lengths, target_freq_offset=target_offset)
		fit_results = measurement.fit.metadata
		if not (int(fit_results['frequency_goodness_test'])):
			raise Exception('Failed to calibrate Ramsey: frequency_goodness_test failed on qubit {}, measurement {}'.format(qubit_id, measurement.id))
		
		# reset frequency?
		frequency_delta = float(fit_results['f']) - target_offset
		num_delta_periods = np.abs(frequency_delta*(np.max(measurement.datasets['iq'+qubit_id].parameters[0].values)-np.min(measurement.datasets['iq'+qubit_id].parameters[0].values)))
		num_decay_periods = np.abs(frequency_delta*float(fit_results['T']))
		if num_delta_periods > 1/8 and num_decay_periods > 1/8 and set_frequency:
			old_frequency = device.get_qubit_fq(qubit_id)
			new_frequency = round((old_frequency+frequency_delta)/frequency_rounding)*frequency_rounding
			device.set_qubit_fq(new_frequency, qubit_id=qubit_id)
			assert(np.abs(frequency_delta) < np.abs(target_offset/2.))
			print('Updating qubit frequency: old frequency {}, new frequency {}'.format(old_frequency, new_frequency))
			device.update_pulsed_frequencies()

		if int(fit_results['decay_goodness_test']):
			return measurement
		
		lengths *= _range
		target_offset /= _range
		
	
	#raise ValueError('Failed measuring Rabi frequency for qubit {} on channel_amplitudes {}'.format(qubit_id, channel_amplitudes.metadata))

def calibrate_all_T2(device):
	for qubit_id in device.get_qubit_list():
		if True: ### TODO check if Ramsey measurement is already there
			Ramsey_adaptive(device, qubit_id, set_frequency=True)
			
def calibrate_all_cross_Ramsey(device):
	cross_Ramsey_fits = {}
	
	for qubit_id in device.get_qubit_list():
		min_step = float(device.get_qubit_constant(qubit_id=qubit_id, name='adaptive_Rabi_min_step'))
		scan_points = int(device.get_qubit_constant(qubit_id=qubit_id, name='adaptive_Rabi_scan_points'))
		points_per_oscillation_target = float(device.get_qubit_constant(qubit_id=qubit_id, name='adaptive_Ramsey_points_per_oscillation'))
		initial_delay = float(device.get_qubit_constant(qubit_id=qubit_id, name='cross_Ramsey_initial_delay')) 	
		target_offset = 1./(min_step*points_per_oscillation_target)
		amplitude_default = float(device.get_qubit_constant(qubit_id=qubit_id, name='amplitude_default'))
		
		lengths = np.arange(initial_delay, min_step*scan_points+initial_delay, min_step)

		cross_Ramsey_fits[qubit_id] = {}

		for channel_name1, device_name1 in device.get_qubit_excitation_channel_list(qubit_id).items():
			ch1 = channel_amplitudes(device, **{channel_name1:amplitude_default})
			try:
				pulse1 = excitation_pulse.get_excitation_pulse(device, qubit_id, np.pi/2., channel_amplitudes_override=ch1)
			except:
				print ('Failed to Rabi-calibrate channel ', channel_name)
				continue
				
			cross_Ramsey_fits[qubit_id][channel_name1] = {}
				
			for channel_name2, device_name2 in device.get_qubit_excitation_channel_list(qubit_id).items():
				ch2 = channel_amplitudes(device, **{channel_name2:amplitude_default})
				try:
					pulse2 = excitation_pulse.get_excitation_pulse(device, qubit_id, np.pi/2., channel_amplitudes_override=ch2)
				except:
					print ('Failed to Rabi-calibrate channel ', channel_name)
					continue
					
				#cross_Ramsey_measurement_results = {}
				cross_Ramsey_measurements = device.exdir_db.select_measurements_db(measurement_type='Ramsey', references_that={'ex_pulse1': pulse1.id, 'ex_pulse2': pulse2.id})
				for m in cross_Ramsey_measurements:
					for r in m.reference_two:
						if r.ref_type=='fit_source':
							fit = r.this
							if int(device.exdir_db.db.Metadata[fit, 'frequency_goodness_test'].value):
								cross_Ramsey_fits[qubit_id][channel_name1][channel_name2] = device.exdir_db.select_measurement_by_id(fit.id)
				if channel_name2 not in cross_Ramsey_fits[qubit_id][channel_name1]: # hasn't been found in db
					Ramsey(device, qubit_id, channel_amplitudes1=ch1, channel_amplitudes2=ch2, lengths=lengths, target_freq_offset=target_offset)
					
	return cross_Ramsey_fits