__author__ = 'gjp'
import sys
import sqlite3 as db
import json

import pika
import clips
import requests

from configuration import RABBITMQ_URL, CLIPS_PATH
from constants import SERVERID
from log import logger
LOGGER_COMPONENT = 'ENVIRONMENT'


def main():
    tenantId = sys.argv[1]

    def env_id():
        return clips.Symbol(sys.argv[1])

    # the following dictionary will contain the environment specific functions
    ENV_SPECIFIC_FUNCTIONS = {}

    # ...and this wrapper calls in turn the functions associated with certain
    #  names for each environment
    def envCallSpecificFunction(e_id, funcname, *args):
        f = ENV_SPECIFIC_FUNCTIONS[e_id][funcname]
        return f(*args)
    clips.RegisterPythonFunction(envCallSpecificFunction, 'env-call-specific-func')

    # now we need some helpers to make it easier to set up the environment and
    #  the map of environment specific functions
    def PrepareEnvironment(e):
        eid = env_id()
        ENV_SPECIFIC_FUNCTIONS[eid] = {}   # a map of functions
        e.Identifier = eid                  # so that we can always get it back
        return eid

    def GetNotificationUrl(ruleName, serverId):
        conn = db.connect("cloto.db")
        conn.row_factory = db.Row
        cur = conn.cursor()
        SQL = "SELECT url from cloto_subscription S join cloto_specificrule R on S.ruleId=R.specificRule_Id " \
              "WHERE name='%s' AND S.serverId='%s';" \
              % (ruleName, serverId)
        cur.execute(SQL)
        while True:
            r = cur.fetchone()
            if not r:
                conn.close()
                break
            else:
                url = r['url']
        return url

    def NotifyEmail(serverId, url, description, email):
        """Sends a notification to given url showing that service must send an email to an address.
        """

        headers = {'Content-Type': 'application/json'}
        data = '{"action": "notifyEmail", "serverId": "' + serverId\
               + ', "email": "' + email + '", "description": "' + description + '"}'
        logger.info("Preparing eMail to %s: %s--- Response: " % (url, data))

        """r = requests.post(url, data=data, headers=headers)
        if r.status_code == 200:
            logger.info("mail sent to %s about server %s.--- Response: %d" % (email, serverId, url, r.status_code))
        else:
            print(2)
            logger.info("ERROR Sending mail to %s about server %s.--- %s Response: %d"
                        % (email, serverId, url, r.status_code))
        """

    def NotifyScale(serverId, url, action):
        """Sends a notification to given url showing that service must scale up or scale down a server.
        """
        headers = {'Content-Type': 'application/json'}
        data = '{"action": "' + action + '", "serverId": "' + serverId + '"}'
        logger.info(action + " message sent to %s : %s"
                        % (url, data))
        """r = requests.post(url, data=data, headers=headers)
        if r.status_code == 200:
            logger.info(action + " message sent to %s about server %s.--- Response: %d"
                        % (url, serverId, r.status_code))
        else:
            logger.error(action + " message sent to %s about server %s.--- Response: %d"
                         % (url, serverId, r.status_code))"""

    def AddSpecificFunction(e, func, funcname=None):
        try:
            eid = e.Identifier
        except:
            raise ValueError("The Environment has not been prepared")
        if funcname is None:
            funcname = func.__name__    # if needed
        ENV_SPECIFIC_FUNCTIONS[eid][funcname] = func
        num_args = func.func_code.co_argcount
        seq_args = " ".join(['?a%s' % x for x in range(num_args)])
        e.BuildFunction(
            funcname,
            seq_args,
            "(return (python-call env-call-specific-func %s %s %s))" % (
                eid, funcname, seq_args))

    def get_rules_from_db(tenantId):
        """Gets all subscripted rules for a specified tenant and adds them to CLIPS environment to be checked.
        """
        import sqlite3 as db
        conn = db.connect("cloto.db")
        conn.row_factory = db.Row
        cur = conn.cursor()
        SQL = "SELECT * FROM cloto_specificrule WHERE specificRule_Id IN " \
              "(SELECT ruleId FROM cloto_subscription WHERE %s IN " \
              "(SELECT %s FROM cloto_entity WHERE tenantId='%s'))" % (SERVERID, SERVERID, tenantId)
        cur.execute(SQL)
        while True:
            r = cur.fetchone()
            if not r:
                conn.close()
                break
            else:
                rule_name = r['name']
                rule_cond = r['condition']
                rule_action = r['action']
                e1.BuildRule(rule_name, rule_cond, rule_action)
    clips.Reset()
    e1 = clips.Environment()
    PrepareEnvironment(e1)
    clips.RegisterPythonFunction(NotifyEmail, "notify-email")
    clips.RegisterPythonFunction(NotifyScale, "notify-scale")
    clips.RegisterPythonFunction(GetNotificationUrl, "get-notification-url")
    e1.Assert("(initial-fact)")

    try:

        connection = pika.BlockingConnection(pika.ConnectionParameters(
                host=RABBITMQ_URL))
        channel = connection.channel()

        channel.exchange_declare(exchange="facts",
                                 exchange_type='direct')

        result = channel.queue_declare(exclusive=True)
        queue_name = result.method.queue

        channel.queue_bind(exchange="facts",
                           queue=queue_name,
                           routing_key=tenantId)

        logger.info('Environment started. Waiting for Facts')

        def callback(ch, method, properties, body):
            try:
                decoded = json.loads(body)
                logger.info(decoded)

                f1 = e1.Assert("(ServerFact \"" + str(decoded[SERVERID]) + "\" " + str(decoded['cpu'])
                               + " " + str(decoded['mem']) + ")")
                logger.info("received fact: %s" % body)
                get_rules_from_db(tenantId)
                e1.PrintFacts()
                e1.PrintRules()
                e1.Run()
                f1.Retract()
            except ValueError:
                logger.error("receiving an invalid body: " + body)
            except clips.ClipsError:
                logger.error(clips.ErrorStream.Read())
            except Exception as ex:
                logger.warn("FACT: already exists")

            e1.PrintFacts()
            e1.PrintRules()

        channel.basic_consume(callback,
                              queue=queue_name,
                              no_ack=True)

        channel.start_consuming()
    except db.Error, e:
        logger.error("%s %s Error %s:" % LOGGER_COMPONENT, tenantId, e.args[0])
    except Exception as ex:
        if ex.message:
            logger.error("%s %s Error %s:" % LOGGER_COMPONENT, tenantId, ex.message)
    finally:
        connection.close()

if __name__ == '__main__':
    main()