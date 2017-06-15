import telebot
import cfg

bot = telebot.TeleBot(cfg.token)

@bot.message_handler(content_types=['text'])
def new_post(message):
	sid = message.chat.id
	
	bot.send_message(sid, bs.thanks, reply_markup=markup)


if __name__ == '__main__':
	bot.polling(none_stop=True)
