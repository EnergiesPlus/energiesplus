=====================================
   Payconiq Payment Acquirer
=====================================

This module enables payments on website through Payoniq.

Please note that:

* This implementation only support V3 of Payconiq API. Be sure to follow closely Payconiq's evolution of this version.


Installation notes
==================

After installing the module configure the payment acquirer in **Website Admin > Configuration > Payment Aquirers**

You will have to set the two key provided by PayConiq:

* merchant_ID
* secret_key

You will also have to provide to PayConiq your callback URL which will be in the form:

* odoo_website_root/payment/payconiq/callback


You can use the build in environment switcher to switch between Dev/Test and Production values.
This module will adapt and reach the corresponding REST server at PayConiq.

Support possible at <odoo@abakusitsolutions.eu>

Credits
=======

Contributors
------------

* Paul Ntabuye Butera
* Arbi Ampukajev <arbi.ampukajev@abakusitsolutions.eu>
* Valentin Thirion <valentin.thirion@abakusitsolutions.eu>

Maintainer
-----------

.. image:: http://www.abakusitsolutions.eu/wp-content/themes/abakus/images/logo.gif
   :alt: AbAKUS IT SOLUTIONS
   :target: http://www.abakusitsolutions.eu

This module is maintained by AbAKUS IT SOLUTIONS
