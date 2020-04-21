from django.utils import timezone

from .models import Distribution, Provider, PatientAssignmentLineItem, Patient


def date_str_to_date(date_str):
    return timezone.datetime.strptime(date_str, '%Y-%m-%d').date()


def helper_fxn_create_distribution_with_4_sample_line_items():
    distribution = Distribution.objects.create()
    abbreviations = ['provA', 'provB', 'provC', 'provD']
    totals = [10, 11, 13, 11]
    CCUs = [2, 3, 2, 1]
    COVIDs = [0, 3, 1, 2]
    orders = [3, 1, 2, 4]
    for i in range(4):
        provider = Provider.objects.get_or_create(abbreviation=abbreviations[i])[0]
        starting_total = totals[i]
        starting_CCU = CCUs[i]
        starting_COVID = COVIDs[i]
        order = orders[i]
        PatientAssignmentLineItem.objects.create_line_item(distribution=distribution,
                                                           provider=provider,
                                                           starting_total=starting_total,
                                                           starting_CCU=starting_CCU,
                                                           starting_COVID=starting_COVID,
                                                           position_in_batting_order=order)


def helper_fxn_create_distribution_with_up_to_4_sample_line_items(line_item_count=4):
    distribution = Distribution.objects.create()
    abbreviations = ['provA', 'provB', 'provC', 'provD']
    totals = [10, 11, 13, 11]
    CCUs = [2, 3, 2, 1]
    COVIDs = [0, 3, 1, 2]
    orders = [3, 1, 2, 4]
    for i in range(line_item_count):
        provider = Provider.objects.get_or_create(abbreviation=abbreviations[i])[0]
        starting_total = totals[i]
        starting_CCU = CCUs[i]
        starting_COVID = COVIDs[i]
        order = orders[i]
        PatientAssignmentLineItem.objects.create_line_item(distribution=distribution,
                                                           provider=provider,
                                                           starting_total=starting_total,
                                                           starting_CCU=starting_CCU,
                                                           starting_COVID=starting_COVID,
                                                           position_in_batting_order=order)


def helper_fxn_create_motley_list_of_patients_assign_to_distribution(patient_count, distribution):
    abbreviations = ['provA', 'provB', 'provC', 'provD']
    for i in range(patient_count):
        covid, ccu, bounce_to = False, False, None
        if i % 2 == 0:
            covid = True
        if i % 3 == 0:
            ccu = True
        if i % 5 == 0:
            bounce_to = Provider.objects.get_or_create(abbreviation=abbreviations[(i // 4) % 5])[0]
        Patient.objects.create(distribution=distribution, number_designation=i + 1, CCU=ccu, COVID=covid,
                               bounce_to=bounce_to)


def helper_fxn_create_list_of_bounceback_patients_assign_to_distribution(patient_count, distribution):
    abbreviations = ['provC', 'provB']
    for i in range(patient_count):
        covid, ccu = False, False
        if i % 2 == 0:
            covid = True
        if i % 3 == 0:
            ccu = True
        bounce_to = Provider.objects.get_or_create(abbreviation=abbreviations[i % 2])[
            0]  # should bounce to LI2, LI3 alt
        Patient.objects.create(distribution=distribution, number_designation=i + 1, CCU=ccu, COVID=covid,
                               bounce_to=bounce_to)
