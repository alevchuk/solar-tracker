CC = gcc
CFLAGS = -Wall -pthread
LDFLAGS = -lm
LIBS = -L /usr/local/include -lpigpio -lrt
INSTALL = `which install`

all: packages collect

clean:
	rm -f collect

packages:
	if ! dpkg-query -W -f='$${Status}' pigpio | grep "ok installed"; then apt-get -y install pigpio; fi

collect: collect.c
	$(CC) $(CFLAGS) collect.c $(LIBS) -o scl3300-d01 $(LDFLAGS)
