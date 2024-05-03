import enquiries
import pendulum

import jira_sync
import toggl

pendulum.week_starts_at(pendulum.MONDAY)


def choose_period():
    options = [
        'This week',
        'Last week',
        'This month',
        'Last month',
        'Custom',
    ]
    choice = enquiries.choose('Choose period to import', options)

    now = pendulum.now()

    start_date = None
    end_date = None

    if choice == 'This week':
        start_date = now.start_of('week')
        end_date = now.add(weeks=1).start_of('week')
    elif choice == 'Last week':
        end_date = now.start_of('week')
        start_date = now.subtract(weeks=1).start_of('week')
    elif choice == 'This month':
        start_date = now.start_of('month')
        end_date = now.add(months=1).start_of('month')
    elif choice == 'Last month':
        end_date = now.start_of('month')
        start_date = now.subtract(months=1).start_of('month')
    elif choice == 'Custom':
        start_date = pendulum.from_format(input('Enter starting date (YYYY-MM-DD): '), 'YYYY-MM-DD')

        if start_date is None:
            print('Invalid start date')
            exit(1)

        end_date = pendulum.from_format(input('Enter ending date (YYYY-MM-DD) (exclusive): '), 'YYYY-MM-DD')

        if end_date is None:
            print('Invalid end date')
            exit(1)

    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')


if __name__ == '__main__':
    start, end = choose_period()

    print('Syncing data from {} to {}'.format(start, end))

    toggl.import_entries(start, end)
    jira_sync.import_to_jira()
