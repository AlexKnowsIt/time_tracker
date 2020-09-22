# Time Tracker to boost Productivity

## Overview

This is a Django project that aims to provide simple planning and tracking of multiple user data and shows them inside an Javascript Dashboard to the specific user. We're using Djano REST-Framework in addition to an implementation of chart.js for data visualization and fullcalendar.io for displaying and editing Events in our planner tool.
We build this upon the idea of user customization in mind. With the implemented REST-APIs you can add your own software to the server to track your hours or synchronize events. If you have a solution that can be used by others as well we're happy if you share your solution via a pull request.

## Usage

As every django project just clone the repository and enable your hosting settings in wsgi. For development purposes after downloading use the commands
python manage.py migrate followed by python manage.py runserver (or on Linux use python3 instead).

## Contributing

We are happy about any contributions and any issue that you can find so feel free to fork, open issues and help us by opening pull requests.

## Recommendations

If you have recommendations for future features also let us know. Just open an issue and we will give our best to implement them.

### To-Dos

- Standard Values should be taken from calendar, so that differences can be applied instead of reqriting the planning by hand.
- Filtering for API Calls for current user (full multi-user support)
- Authentication for Calendar PUT API -> No changes without permission
- REST-API to communicate with bash script and design own add-ons that can communicate via token with the server
- AI to predict optimal workload for next day (maximize average between happiness and productivity)
