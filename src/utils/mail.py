import subprocess


def send_contact_message(first_name, last_name, role, message):
    subject = first_name + " " + last_name + " sent a message from ESP"
    send_mail("admin@uantwerpen.be", subject, message)


def send_mail(address, subject, message):
    """
    Sends a mail using the sendemail command configured on the UA servers

    :param address: the recipient's mail address
    :param subject: the mail subject
    :param message: the mail message
    :return: process return code
    """
    try:
        cmd = ['sendemail', '-f', 'noreply@uantwerpen.be', '-t', address, '-u', subject, '-m', message, '-s',
               'smtp.uantwerpen.be']
        proc = subprocess.Popen(cmd)
        return proc.returncode == 0
    except:
        return False
