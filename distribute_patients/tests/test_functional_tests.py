import time
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.utils import timezone

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.keys import Keys

from contextlib import contextmanager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import staleness_of

from ..helper_fxns import helper_fxn_create_distribution_with_4_sample_line_items
from ..models import Distribution, Patient, Provider, PatientAssignmentLineItem

MAX_WAIT = 3


class FunctionalTests(StaticLiveServerTestCase):
    def setUp(self):
        self.browser = webdriver.Firefox()

    def tearDown(self):
        self.browser.quit()

    @contextmanager
    def wait_for_page_load(self, timeout=30):
        old_page = self.browser.find_element_by_tag_name('html')
        yield
        WebDriverWait(self.browser, timeout).until(
            staleness_of(old_page)
        )

    def wait_for(self, fn):
        start_time = time.time()
        while True:
            time.sleep(1)
            try:
                return fn()
            except (WebDriverException, AssertionError) as e:
                if time.time() - start_time > MAX_WAIT:
                    raise e

class FirstLogin(FunctionalTests):
    def test_if_no_prior_distributions_taken_to_set_rounders_page(self):
        # Jun is logging in for the first time this has ever been used.  She goes to the main page, and is
        # taken to the page to enter in the current rounders
        self.browser.get(f'{self.live_server_url}')
        self.assertEqual(self.browser.title, f'Set Rounders - {timezone.localdate().strftime("%-m/%-d/%y")}')

        # Jun types in the names of the rounders, and submits them, and is taken to the starting census page
        rounder_forms = self.browser.find_elements_by_id('id_rounder_form')
        provider_names = ['provA', 'provB', 'provC', 'provD', 'provE', 'provF', 'provG', 'provH']
        starting_totals = [11, 12, 14, 15, 9, 8, 16, 13]
        starting_CCUs = [2,5,3,7,0,1,1,0]
        starting_COVIDs = [1,2,5,0,3,6,4,3]
        for index, rounder_name in enumerate(provider_names):
            rounder_name_box = rounder_forms[index].find_element_by_id('id_rounder_abbreviation_field')
            rounder_name_box.send_keys(rounder_name)
            rounder_total_box = rounder_forms[index].find_element_by_id('id_starting_total_field')
            rounder_CCU_box = rounder_forms[index].find_element_by_id('id_starting_CCU_field')
            rounder_COVID_box = rounder_forms[index].find_element_by_id('id_starting_COVID_field')
            rounder_total_box.send_keys(starting_totals[index])
            rounder_CCU_box.send_keys(starting_CCUs[index])
            rounder_COVID_box.send_keys(starting_COVIDs[index])
        submit_button = self.browser.find_element_by_id('id_submit_rounder_forms')
        submit_button.click()
        self.wait_for(lambda: self.browser.find_elements_by_tag_name('body'))
        self.assertEqual(self.browser.title, f'Patient Count - {timezone.localdate().strftime("%-m/%-d/%y")}')

         # She notes that the rounders she just typed in have now become the day's rounders
        starting_census_table = self.browser.find_element_by_id('id_starting_census_table')
        rounder_rows = starting_census_table.find_elements_by_id('id_rounder_row')
        for index, rounder_row in enumerate(rounder_rows):
            provider_cell = rounder_row.find_element_by_id('id_provider_cell')
            self.assertEqual(provider_cell.text, provider_names[index])

        self.assertEqual(Distribution.objects.count(), 1)
        self.assertEqual(Distribution.objects.first().line_items.count(), 8)
        for index, line_item in enumerate(Distribution.objects.first().get_ordered_line_items()):
            self.assertEqual(line_item.provider.abbreviation, provider_names[index])
        # She also notes that the census values she put in have become the day's starting census
        for index, rounder_row in enumerate(rounder_rows):
            total_census_cell = rounder_row.find_element_by_id('id_total_census_cell')
            CCU_census_cell = rounder_row.find_element_by_id('id_CCU_census_cell')
            COVID_census_cell = rounder_row.find_element_by_id('id_COVID_census_cell')
            self.assertEqual(int(total_census_cell.text), starting_totals[index])
            self.assertEqual(int(CCU_census_cell.text), starting_CCUs[index])
            self.assertEqual(int(COVID_census_cell.text), starting_COVIDs[index])
        for index, line_item in enumerate(Distribution.objects.first().get_ordered_line_items()):
            self.assertEqual(line_item.starting_census.total, starting_totals[index])
            self.assertEqual(line_item.starting_census.CCU, starting_CCUs[index])
            self.assertEqual(line_item.starting_census.COVID, starting_COVIDs[index])
            self.assertEqual(line_item.assigned_census.total, starting_totals[index])
            self.assertEqual(line_item.assigned_census.CCU, starting_CCUs[index])
            self.assertEqual(line_item.assigned_census.COVID, starting_COVIDs[index])

        # Jun types in the count, submits, and is taken to the patient_designation page
        patients_to_distribute_box = self.browser.find_element_by_id('id_count_to_distribute')
        self.assertEqual(patients_to_distribute_box.get_attribute('value'), '')
        patients_to_distribute_box.send_keys('23')
        patients_to_distribute_box.send_keys(Keys.ENTER)
        self.wait_for(lambda: self.browser.find_elements_by_tag_name('body'))
        self.assertEqual(self.browser.title, f'Designate Patients - {timezone.localdate().strftime("%-m/%-d/%y")}')

        # Jun designates the patients, submits and is taken to the patient_assignment page
        self.wait_for(lambda: self.browser.find_elements_by_tag_name('body'))
        self.assertEqual(self.browser.title, f'Designate Patients - {timezone.localdate().strftime("%-m/%-d/%y")}')
        patient_cards = self.browser.find_elements_by_class_name('patient-card')
        for i in [0, 13, 14]:
            patient_cards[i].find_element_by_class_name('CCU-checkbox').click()
            patient_cards[i].find_element_by_class_name('COVID-checkbox').click()
        for i in [1,5,7,16]:
            patient_cards[i].find_element_by_class_name('COVID-checkbox').click()
        for i in [2,8,9]:
            patient_cards[i].find_element_by_class_name('CCU-checkbox').click()
        submit_patient_forms_button = self.browser.find_element_by_id('id_submit_patient_forms')
        submit_patient_forms_button.click()
        self.wait_for(lambda: self.browser.find_elements_by_tag_name('body'))
        self.assertEqual(self.browser.title, f'Patient Assignments - {timezone.localdate().strftime("%-m/%-d/%y")}')



class EditCountPage(FunctionalTests):
    def test_entering_patient_count_creates_patients_and_redirects_to_designate_patients(self):
        helper_fxn_create_distribution_with_4_sample_line_items()
        self.browser.get(f'{self.live_server_url}/distribute/edit_count/')
        self.assertEqual(self.browser.title, f'Patient Count - {timezone.localdate().strftime("%-m/%-d/%y")}')
        patients_to_distribute_box = self.browser.find_element_by_id('id_count_to_distribute')
        self.assertEqual(patients_to_distribute_box.get_attribute('value'), '')
        patients_to_distribute_box.send_keys('23')
        patients_to_distribute_box.send_keys(Keys.ENTER)
        self.wait_for(lambda: self.browser.find_elements_by_tag_name('body'))
        self.assertEqual(self.browser.title, f'Designate Patients - {timezone.localdate().strftime("%-m/%-d/%y")}')
        self.assertEqual(Distribution.objects.count(), 1)
        self.assertEqual(Patient.objects.count(), 23)
        for index, patient in enumerate(Patient.objects.all()):
            self.assertEqual(patient.distribution, Distribution.objects.first())
            self.assertEqual(patient.number_designation, index + 1)


class DesignatePatientsPage(FunctionalTests):


    def test_marking_COVID_and_CCU_and_submitting_page_adjusts_those_patient_characteristics(self):
        helper_fxn_create_distribution_with_4_sample_line_items()
        self.browser.get(f'{self.live_server_url}/distribute/edit_count/')
        self.assertEqual(self.browser.title, f'Patient Count - {timezone.localdate().strftime("%-m/%-d/%y")}')
        patients_to_distribute_box = self.browser.find_element_by_id('id_count_to_distribute')
        self.assertEqual(patients_to_distribute_box.get_attribute('value'), '')
        patients_to_distribute_box.send_keys('23')
        patients_to_distribute_box.send_keys(Keys.ENTER)
        self.wait_for(lambda: self.browser.find_elements_by_tag_name('body'))
        self.assertEqual(self.browser.title, f'Designate Patients - {timezone.localdate().strftime("%-m/%-d/%y")}')
        patient_cards = self.browser.find_elements_by_class_name('patient-card')
        for i in [0, 13, 14]:
            patient_cards[i].find_element_by_class_name('CCU-checkbox').click()
            patient_cards[i].find_element_by_class_name('COVID-checkbox').click()
        submit_patient_forms_button = self.browser.find_element_by_id('id_submit_patient_forms')
        submit_patient_forms_button.click()
        self.wait_for(lambda: self.browser.find_elements_by_tag_name('body'))
        self.assertEqual(self.browser.title, f'Patient Assignments - {timezone.localdate().strftime("%-m/%-d/%y")}')
        for i in range(23):
            patient = Patient.objects.all()[i]
            if i in [0, 13, 14]:
                self.assertTrue(patient.CCU)
                self.assertTrue(patient.COVID)
            else:
                self.assertFalse(patient.CCU)
                self.assertFalse(patient.COVID)

    def test_marking_COVID_and_CCU_and_submitting_redirects_to_patient_assignments(self):
        helper_fxn_create_distribution_with_4_sample_line_items()
        self.browser.get(f'{self.live_server_url}/distribute/edit_count/')
        self.assertEqual(self.browser.title, f'Patient Count - {timezone.localdate().strftime("%-m/%-d/%y")}')
        patients_to_distribute_box = self.browser.find_element_by_id('id_count_to_distribute')
        self.assertEqual(patients_to_distribute_box.get_attribute('value'), '')
        patients_to_distribute_box.send_keys('23')
        patients_to_distribute_box.send_keys(Keys.ENTER)
        self.wait_for(lambda: self.browser.find_elements_by_tag_name('body'))
        self.assertEqual(self.browser.title, f'Designate Patients - {timezone.localdate().strftime("%-m/%-d/%y")}')
        patient_cards = self.browser.find_elements_by_class_name('patient-card')
        for i in [0, 13, 14]:
            patient_cards[i].find_element_by_class_name('CCU-checkbox').click()
            patient_cards[i].find_element_by_class_name('COVID-checkbox').click()
        for i in [1,5,7,16]:
            patient_cards[i].find_element_by_class_name('COVID-checkbox').click()
        for i in [2,8,9]:
            patient_cards[i].find_element_by_class_name('CCU-checkbox').click()
        submit_patient_forms_button = self.browser.find_element_by_id('id_submit_patient_forms')
        submit_patient_forms_button.click()
        self.wait_for(lambda: self.browser.find_elements_by_tag_name('body'))
        self.assertEqual(self.browser.title, f'Patient Assignments - {timezone.localdate().strftime("%-m/%-d/%y")}')
        pass